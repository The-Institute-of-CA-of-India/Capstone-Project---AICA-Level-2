"""Run this file in IDLE (F5), then visit http://127.0.0.1:5000."""
from pathlib import Path
import os
import secrets
import sqlite3
from contextlib import closing
from flask import Flask, abort, flash, g, jsonify, redirect, render_template, request, send_from_directory, session, url_for
from content import LESSONS, CURRICULUM, FORMULAS, PLACEMENT
from practice import grade

ROOT = Path(__file__).resolve().parent

def create_app(test_config=None):
    app = Flask(__name__)
    secret = os.environ.get('FLASK_SECRET_KEY')
    if not secret:
        secret_path = ROOT/'instance'/'session-secret.txt'
        secret_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with secret_path.open('x', encoding='utf-8') as file:
                file.write(secrets.token_hex(32))
        except FileExistsError:
            pass
        secret = secret_path.read_text(encoding='utf-8').strip()
    app.config.update(SECRET_KEY=secret, DATABASE=str(ROOT/'instance'/'learning.sqlite3'), SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax', MAX_CONTENT_LENGTH=16000)
    if test_config:
        app.config.update(test_config)
    Path(app.config['DATABASE']).parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(app.config['DATABASE'])) as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS learners (id TEXT PRIMARY KEY, name TEXT NOT NULL DEFAULT 'Learner', placement TEXT);
        CREATE TABLE IF NOT EXISTS progress (learner TEXT, lesson INTEGER, visited INTEGER DEFAULT 0, practice INTEGER DEFAULT 0, best INTEGER DEFAULT 0, bookmark INTEGER DEFAULT 0, PRIMARY KEY(learner,lesson));
        CREATE TABLE IF NOT EXISTS attempts (id INTEGER PRIMARY KEY, learner TEXT, lesson INTEGER, score INTEGER, answers TEXT, created TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS achievements (learner TEXT, badge TEXT, created TEXT DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(learner,badge));
        ''')

    def db():
        if 'db' not in g:
            g.db = sqlite3.connect(app.config['DATABASE'])
            g.db.row_factory = sqlite3.Row
        return g.db

    @app.teardown_appcontext
    def close_db(error):
        connection = g.pop('db', None)
        if connection:
            connection.close()

    @app.before_request
    def identify():
        # A local browser profile, not a public authentication system.
        if 'learner' not in session:
            session['learner'] = secrets.token_urlsafe(24)
        session.setdefault('csrf', secrets.token_urlsafe(24))
        db().execute('INSERT OR IGNORE INTO learners(id) VALUES (?)', (session['learner'],))
        db().commit()
        if request.method == 'POST':
            token = request.headers.get('X-CSRF-Token') if request.is_json else request.form.get('csrf')
            if not token or not secrets.compare_digest(token, session['csrf']):
                abort(400, 'This form expired. Reload the page and try again.')

    def state():
        return {r['lesson']:dict(r) for r in db().execute('SELECT * FROM progress WHERE learner=?',(session['learner'],))}

    def update(lesson_id, field, value):
        if field not in ('visited','practice','best','bookmark'):
            raise ValueError('Unknown progress field')
        db().execute('INSERT OR IGNORE INTO progress(learner,lesson) VALUES (?,?)',(session['learner'],lesson_id))
        db().execute(f'UPDATE progress SET {field}=? WHERE learner=? AND lesson=?',(value,session['learner'],lesson_id))
        db().commit()

    def completed(p):
        return p.get('practice',0) and p.get('best',0) >= 80

    def award():
        count = sum(bool(completed(p)) for p in state().values())
        for threshold, badge in [(1,'First steps'),(3,'Building momentum'),(5,'Foundation finisher')]:
            if count >= threshold:
                db().execute('INSERT OR IGNORE INTO achievements(learner,badge) VALUES (?,?)',(session['learner'],badge))
        db().commit()

    def lesson_or_404(lesson_id):
        if not 1 <= lesson_id <= len(LESSONS):
            abort(404)
        return LESSONS[lesson_id-1]

    @app.context_processor
    def shared():
        progress = state()
        learner = db().execute('SELECT * FROM learners WHERE id=?',(session['learner'],)).fetchone()
        done = sum(bool(completed(p)) for p in progress.values())
        next_id = next((l['id'] for l in LESSONS if not completed(progress.get(l['id'],{}))),1)
        return dict(lessons=LESSONS, curriculum=CURRICULUM, progress=progress, done=done, next_lesson=LESSONS[next_id-1], learner=learner, is_complete=completed, csrf=session['csrf'])

    @app.route('/')
    def home():
        badges = [r[0] for r in db().execute('SELECT badge FROM achievements WHERE learner=?',(session['learner'],))]
        return render_template('home.html', page='home', badges=badges)

    @app.route('/courses')
    def courses():
        return render_template('courses.html',page='courses')

    @app.route('/lesson/<int:lesson_id>')
    def lesson(lesson_id):
        item = lesson_or_404(lesson_id)
        update(lesson_id,'visited',1)
        session['last_lesson'] = lesson_id
        return render_template('lesson.html',page='courses',lesson=item)

    @app.post('/lesson/<int:lesson_id>/bookmark')
    def bookmark(lesson_id):
        lesson_or_404(lesson_id)
        update(lesson_id,'bookmark',1-state().get(lesson_id,{}).get('bookmark',0))
        return redirect(url_for('lesson',lesson_id=lesson_id))

    @app.post('/lesson/<int:lesson_id>/practice')
    def practice(lesson_id):
        lesson_or_404(lesson_id)
        data = request.get_json(silent=True)
        if not isinstance(data,dict):
            return jsonify(error='Expected a JSON object.'),400
        ok, message = grade(lesson_id,data.get('answer',''))
        if ok:
            update(lesson_id,'practice',1)
            award()
        return jsonify(correct=ok,message=message)

    def score_quiz(questions):
        answers = []
        for i,q in enumerate(questions):
            try:
                answer = int(request.form[f'q{i}'])
            except (KeyError,ValueError):
                abort(400,'Answer every question, then submit again.')
            if not 0 <= answer < len(q['options']):
                abort(400,'Invalid answer option.')
            answers.append(answer)
        score = round(100*sum(a == q['answer'] for a,q in zip(answers,questions))/len(questions))
        return answers, score

    @app.post('/lesson/<int:lesson_id>/quiz')
    def quiz(lesson_id):
        item = lesson_or_404(lesson_id)
        answers, score = score_quiz(item['quiz'])
        db().execute('INSERT INTO attempts(learner,lesson,score,answers) VALUES (?,?,?,?)',(session['learner'],lesson_id,score,','.join(map(str,answers))))
        update(lesson_id,'best',max(score,state().get(lesson_id,{}).get('best',0)))
        award()
        return render_template('result.html',page='courses',questions=item['quiz'],answers=answers,score=score,lesson=item)

    @app.route('/placement',methods=['GET','POST'])
    def placement():
        if request.method == 'POST':
            answers,score = score_quiz(PLACEMENT)
            level = 'Beginner' if score < 75 else 'Intermediate'
            db().execute('UPDATE learners SET placement=? WHERE id=?',(level,session['learner']))
            db().execute('INSERT INTO attempts(learner,lesson,score,answers) VALUES (?,0,?,?)',(session['learner'],score,','.join(map(str,answers))))
            db().commit()
            return render_template('result.html',page='courses',questions=PLACEMENT,answers=answers,score=score,recommendation=level)
        return render_template('placement.html',page='courses',questions=PLACEMENT)

    @app.route('/formulas')
    def formulas():
        return render_template('formulas.html',page='formulas',formulas=FORMULAS)

    @app.route('/progress')
    def dashboard():
        attempts = db().execute('SELECT lesson,score,created FROM attempts WHERE learner=? ORDER BY id DESC LIMIT 20',(session['learner'],)).fetchall()
        badges = [r[0] for r in db().execute('SELECT badge FROM achievements WHERE learner=?',(session['learner'],))]
        return render_template('progress.html',page='progress',attempts=attempts,badges=badges)

    @app.post('/profile')
    def profile():
        name = request.form.get('name','').strip()[:40] or 'Learner'
        db().execute('UPDATE learners SET name=? WHERE id=?',(name,session['learner']))
        db().commit()
        flash('Your display name is saved.')
        return redirect(url_for('dashboard'))

    @app.route('/coach',methods=['GET','POST'])
    def coach():
        selected = request.args.get('lesson',session.get('last_lesson',1),type=int) or 1
        if request.method == 'POST':
            selected = request.form.get('lesson',1,type=int) or 1
        item = lesson_or_404(selected)
        reply = None
        if request.method == 'POST':
            action = request.form.get('action','simple')
            replies = {'simple':item['explanation'], 'advanced':item['example']+' Check your understanding: explain why each step works before changing the inputs.', 'hint1':item['hints'][0],'hint2':item['hints'][1],'solution':item['hints'][2], 'practice':item['challenge'], 'errors':'#DIV/0!: check a zero or empty denominator. #NAME?: check function spelling and unsupported functions. #REF!: a referenced cell may have been deleted. #VALUE!: check whether text is being used where a number is expected. '+item['mistakes'][0]}
            if action == 'revision':
                weak = [l['title'] for l in LESSONS if state().get(l['id'],{}).get('visited') and state().get(l['id'],{}).get('best',0)<80]
                reply = 'Revisit: '+', '.join(weak)+'. Read each quiz explanation and retry.' if weak else 'Continue with your next unfinished lesson. You can revisit any lesson at any time.'
            else:
                reply = replies.get(action,item['explanation'])
        return render_template('coach.html',page='coach',lesson=item,reply=reply)

    @app.route('/download/<int:lesson_id>/<kind>')
    def download(lesson_id,kind):
        lesson_or_404(lesson_id)
        if kind not in ('practice','solution'):
            abort(404)
        return send_from_directory(ROOT/'downloads',f'lesson-{lesson_id}-{kind}.xlsx',as_attachment=True)

    @app.errorhandler(400)
    @app.errorhandler(404)
    @app.errorhandler(413)
    def error(error):
        return render_template('error.html',page='',error=error),error.code

    return app

if __name__ == '__main__':
    create_app().run(host='127.0.0.1', port=5000, debug=False)
