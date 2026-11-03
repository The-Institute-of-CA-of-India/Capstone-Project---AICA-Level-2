"""Run: python -m unittest -v. Uses disposable SQLite databases."""
import tempfile
import unittest
from pathlib import Path
from app import create_app
from content import LESSONS
from practice import grade, calculate

class LearningJourneyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.config = dict(TESTING=True,SECRET_KEY='test-only',DATABASE=str(Path(self.temp.name)/'test.db'))
        self.app=create_app(self.config)
        self.client=self.app.test_client()
        self.client.get('/')
        with self.client.session_transaction() as session:
            self.csrf=session['csrf']

    def tearDown(self):
        self.temp.cleanup()

    def test_pages_downloads_and_errors(self):
        for path in ['/','/courses','/formulas','/progress','/placement','/coach']+[f'/lesson/{i}' for i in range(1,6)]:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code,200)
        for i in range(1,6):
            for kind in ['practice','solution']:
                response=self.client.get(f'/download/{i}/{kind}')
                self.assertEqual(response.status_code,200)
                self.assertTrue(response.data.startswith(b'PK'))
                self.assertIn('attachment',response.headers['Content-Disposition'])
                response.close()
        for path in ['/lesson/99','/download/1/bad','/not-found','/coach?lesson=99']:
            self.assertEqual(self.client.get(path).status_code,404)
        self.assertEqual(self.client.post('/lesson/1/quiz',data={'csrf':self.csrf}).status_code,400)
        self.assertEqual(self.client.post('/profile',data={'name':'Oops'}).status_code,400)
        response=self.client.post('/lesson/1/practice',json=['bad'],headers={'X-CSRF-Token':self.csrf})
        self.assertEqual(response.status_code,400)

    def test_complete_journey_and_reopen(self):
        for item in LESSONS:
            i=item['id']
            self.client.get(f'/lesson/{i}')
            correct=self.client.post(f'/lesson/{i}/practice',json={'answer':item['answer']},headers={'X-CSRF-Token':self.csrf})
            self.assertTrue(correct.json['correct'])
            data={'csrf':self.csrf,**{f'q{n}':str(q['answer']) for n,q in enumerate(item['quiz'])}}
            response=self.client.post(f'/lesson/{i}/quiz',data=data)
            self.assertIn(b'100%',response.data)
            self.assertIn(b'Lesson complete',response.data)
        self.assertIn(b'5 / 5 complete',self.client.get('/progress').data)
        self.assertIn(b'Earned',self.client.get('/progress').data)
        # A lower retry must not erase the best score.
        self.client.post('/lesson/1/quiz',data={'csrf':self.csrf,'q0':'1','q1':'0'})
        self.assertIn(b'Best quiz: 100%',self.client.get('/progress').data)
        self.client.post('/lesson/1/bookmark',data={'csrf':self.csrf})
        self.assertIn(b'Bookmarked',self.client.get('/lesson/1').data)
        self.client.post('/profile',data={'csrf':self.csrf,'name':'<script>test</script>'})
        self.assertIn(b'&lt;script&gt;',self.client.get('/progress').data)
        cookie=self.client.get_cookie('session')
        reopened=create_app(self.config).test_client()
        reopened.set_cookie('session',cookie.value)
        self.assertIn(b'5 / 5 complete',reopened.get('/progress').data)
        other=self.app.test_client()
        self.assertIn(b'0 / 5 complete',other.get('/progress').data)

    def test_placement_and_coach(self):
        response=self.client.post('/placement',data={'csrf':self.csrf,'q0':'0','q1':'1','q2':'0','q3':'0'})
        self.assertIn(b'Intermediate',response.data)
        for action in ['simple','advanced','hint1','hint2','solution','errors','practice','revision']:
            response=self.client.post('/coach',data={'csrf':self.csrf,'lesson':'4','action':action})
            self.assertEqual(response.status_code,200)
            self.assertIn(b'PREPARED COURSE GUIDANCE',response.data)

    def test_grader_accepts_equivalents_and_rejects_unsafe_code(self):
        for formula in ['=(B2+B3)*2','=B2*2+B3*2','=SUM(B2:B3)*2']:
            self.assertTrue(grade(4,formula)[0])
        for formula in ['=SUM(B2:B5)','=B2+B3+B4+B5','=sum($B$2:$B$5)']:
            self.assertTrue(grade(5,formula)[0])
        for formula in ['=80','=B2+B3',"=__import__('os').system('x')",'=B2**999999','=SUM(B2:B6)','=B2/0']:
            self.assertFalse(grade(5,formula)[0])
        self.assertFalse(grade(1,{'bad':'value'})[0])
        self.assertEqual(calculate('=AVERAGE(B2:B5)',dict(B2=40,B3=20,B4=8,B5=12)),20)

if __name__=='__main__':
    unittest.main()
