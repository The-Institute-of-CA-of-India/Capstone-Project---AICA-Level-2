import fs from 'node:fs';
import vm from 'node:vm';
import crypto from 'node:crypto';
import assert from 'node:assert/strict';
const root=new URL('../',import.meta.url), source=fs.readFileSync(new URL('Code.gs',root),'utf8').replace(/^\uFEFF/,'');
assert.doesNotMatch(source, /\?\?=|&&=|\|\|=/, 'Server code must not use Apps Script-incompatible logical assignment');
let user='aicadipal@gmail.com',effective=user,quota=50,sent=[],sendThrows=false,locked=false;
const users=new Map(),databases=new Map();let serial=0;
class Range{constructor(sheet,r,c,n=1,m=1){Object.assign(this,{sheet,r,c,n,m})}setValues(values){assert.equal(values.length,this.n);for(let i=0;i<this.n;i++){assert.equal(values[i].length,this.m);for(let j=0;j<this.m;j++){this.sheet.rows[this.r-1+i]??=[];this.sheet.rows[this.r-1+i][this.c-1+j]=values[i][j]}}return this}getValues(){return Array.from({length:this.n},(_,i)=>Array.from({length:this.m},(_,j)=>this.sheet.rows[this.r-1+i]?.[this.c-1+j]??''))}getValue(){return this.getValues()[0][0]}}
class Sheet{constructor(name){this.name=name;this.rows=[];this.max=1000}getRange(...args){return new Range(this,...args)}getLastRow(){let n=this.rows.length;while(n&&!this.rows[n-1]?.some(v=>v!==''&&v!==undefined))n--;return n}getMaxRows(){return this.max}insertRowsAfter(_,n){this.max+=n}getDataRange(){let n=Math.max(1,this.getLastRow()),m=Math.max(1,...this.rows.map(r=>r.length));return this.getRange(1,1,n,m)}clearContents(){this.rows=[]}setFrozenRows(){}}
class DB{constructor(name){this.name=name;this.id='sheet-'+(++serial);this.owner=user;this.sheets=new Map()}getSheetByName(n){return this.sheets.get(n)||null}insertSheet(n){let s=new Sheet(n);this.sheets.set(n,s);return s}getId(){return this.id}getUrl(){return 'https://docs.google.com/spreadsheets/d/'+this.id+'/edit'}}
const ctx={console,Date,JSON,Set,Math,Error,String,Array,Number,Boolean,
 Session:{getActiveUser:()=>({getEmail:()=>user}),getEffectiveUser:()=>({getEmail:()=>effective})},
 LockService:{getScriptLock:()=>({tryLock:()=>{if(locked)return false;locked=true;return true},releaseLock:()=>{locked=false}})},
 PropertiesService:{getUserProperties:()=>{if(!users.has(user))users.set(user,new Map());let p=users.get(user);return {getProperty:k=>p.get(k)||null,setProperty:(k,v)=>p.set(k,v)}}},
 SpreadsheetApp:{create:name=>{let s=new DB(name);databases.set(s.id,s);return s},openById:id=>{let s=databases.get(id);if(!s||s.owner!==user)throw Error('access denied');return s},flush(){}},
 MailApp:{getRemainingDailyQuota:()=>quota,sendEmail:msg=>{sent.push({...msg,user});if(sendThrows)throw Error('simulated transport failure');quota--}},
 Utilities:{getUuid:()=>crypto.randomUUID(),DigestAlgorithm:{SHA_256:'sha256'},Charset:{UTF_8:'utf8'},computeDigest:(_,s)=>[...crypto.createHash('sha256').update(s,'utf8').digest()],base64EncodeWebSafe:v=>Buffer.from(typeof v==='string'?v:Uint8Array.from(v)).toString('base64url'),base64DecodeWebSafe:s=>[...Buffer.from(s,'base64url')],newBlob:b=>({getDataAsString:()=>Buffer.from(b).toString('utf8')})}
};vm.createContext(ctx);vm.runInContext(source,ctx);
const passed=[];function test(name,fn){fn();passed.push(name)}
const clone=v=>JSON.parse(JSON.stringify(v));const fail=(fn,pattern)=>assert.throws(fn,pattern);
let owner,checker,work;
test('Fresh account requires database setup',()=>assert.equal(ctx.pdBootstrap().needsSetup,true));
test('Creates owner database without sending email',()=>{owner=ctx.pdCreateWorkspace();assert.equal(owner.email,user);assert.equal(owner.revision,1);assert.equal(sent.length,0)});
test('Setup is idempotent',()=>assert.equal(ctx.pdCreateWorkspace().spreadsheetId,owner.spreadsheetId));
test('Second account has independent setup',()=>{user=effective='checker@example.com';assert.equal(ctx.pdBootstrap().needsSetup,true);checker=ctx.pdCreateWorkspace();assert.notEqual(checker.spreadsheetId,owner.spreadsheetId)});
test('Checker cannot access owner database via user properties',()=>{users.get(user).set('PD_DATABASE_V2',owner.spreadsheetId);fail(()=>ctx.pdBootstrap(),/DATABASE/);users.get(user).set('PD_DATABASE_V2',checker.spreadsheetId)});
test('Deploy-as-owner identity mismatch rejected',()=>{effective='aicadipal@gmail.com';fail(()=>ctx.pdBootstrap(),/IDENTITY/);effective=user});
test('Blank identity rejected',()=>{const old=user;user='';fail(()=>ctx.pdBootstrap(),/IDENTITY/);user=effective=old});
user=effective='aicadipal@gmail.com';
work=clone(owner.state);work.clients.push({id:'client-1',name:'Alpha LLP',contact:'A',email:'alpha@example.com',phone:'0123'});work.assignments.push({id:'assignment-1',clientId:'client-1',title:'Audit',period:'FY 2025-26',owner:'Dipal',due:'2026-11-16',created:new Date().toISOString(),notes:'',docs:[{id:'doc-1',name:'Bank statement',required:true,status:'Pending',due:'',receivedOn:'',notes:''}],followUps:[],nextFollowUp:''});
test('Validated state saves and increments revision',()=>assert.equal(ctx.pdSave(work,1,'save-1').revision,2));
test('Lost-response save retry is idempotent',()=>{let r=ctx.pdSave(work,1,'save-1');assert.equal(r.revision,2);assert.equal(r.replayed,true)});
test('Save ID cannot be reused for different payload',()=>{let changed=clone(work);changed.settings.firm='Different';fail(()=>ctx.pdSave(changed,1,'save-1'),/SAVE_ID/)});
test('Concurrent stale save rejected',()=>fail(()=>ctx.pdSave(work,1,'save-2'),/CONFLICT/));
test('Reload returns saved records',()=>assert.equal(ctx.pdBootstrap().state.clients[0].phone,'0123'));
test('Checker sees no owner client records',()=>{user=effective='checker@example.com';assert.equal(ctx.pdBootstrap().state.clients.length,0);user=effective='aicadipal@gmail.com'});
test('Invalid leap date rejected',()=>{let x=clone(work);x.assignments[0].due='2026-02-30';fail(()=>ctx.pdSave(x,2,'bad-date'),/VALIDATION/)});
test('Orphan assignment rejected',()=>{let x=clone(work);x.assignments[0].clientId='missing';fail(()=>ctx.pdSave(x,2,'orphan'),/VALIDATION/)});
test('Duplicate record IDs rejected',()=>{let x=clone(work);x.assignments[0].docs[0].id='client-1';fail(()=>ctx.pdSave(x,2,'dupe'),/VALIDATION/)});
test('Formula text is neutralised in readable tabs',()=>{let x=clone(work);x.clients[0].name='=IMPORTXML("x")';ctx.pdSave(x,2,'save-formula');let db=databases.get(owner.spreadsheetId);assert.ok(String(db.getSheetByName('Clients').rows[1][1]).startsWith("'="));work=x});
test('Readable tabs can be repaired',()=>assert.equal(ctx.pdRepairViews().revision,3));
test('Health check does not send email',()=>{const n=sent.length;assert.equal(ctx.pdSelfTest().snapshotVerified,true);assert.equal(sent.length,n)});
const req={id:'email-1',to:'owner-test@example.com',subject:'Test',body:'A reviewed test message.',assignmentId:'assignment-1'};
test('Email sends as authorized owner',()=>{let r=ctx.pdSendEmail(req);assert.equal(r.status,'Sent (accepted)');assert.equal(sent[0].user,'aicadipal@gmail.com');assert.equal(sent[0].replyTo,user)});
test('Same email request is not sent twice',()=>{const n=sent.length;assert.equal(ctx.pdSendEmail(req).replayed,true);assert.equal(sent.length,n)});
test('Changed content cannot reuse email ID',()=>fail(()=>ctx.pdSendEmail({...req,body:'Changed'}),/REQUEST_ID/));
test('Identical new request blocked for ten minutes',()=>{let n=sent.length;fail(()=>ctx.pdSendEmail({...req,id:'email-2'}),/DUPLICATE/);assert.equal(sent.length,n)});
test('Header injection / multiple recipients rejected',()=>{fail(()=>ctx.pdSendEmail({...req,id:'invalid',to:'a@example.com,b@example.com'}),/VALIDATION/);fail(()=>ctx.pdSendEmail({...req,id:'inject',subject:'Hello\r\nBcc: x@example.com'}),/VALIDATION/)});
test('Quota exhaustion prevents send',()=>{quota=0;const n=sent.length;fail(()=>ctx.pdSendEmail({...req,id:'quota-test',subject:'Quota test'}),/QUOTA/);assert.equal(sent.length,n);quota=50});
test('Unknown send outcome is not retried',()=>{sendThrows=true;const r=ctx.pdSendEmail({...req,id:'unknown-send',subject:'Transport test'});assert.equal(r.status,'Unknown');sendThrows=false;const n=sent.length;assert.equal(ctx.pdSendEmail({...req,id:'unknown-send',subject:'Transport test'}).replayed,true);assert.equal(sent.length,n)});
test('Checker sends only through checker account',()=>{user=effective='checker@example.com';let r=ctx.pdSendEmail({...req,id:'checker-test',assignmentId:'',to:'checker@example.com'});assert.equal(r.status,'Sent (accepted)');assert.equal(sent.at(-1).user,user);assert.equal(ctx.pdBootstrap().emails.length,1);user=effective='aicadipal@gmail.com'});
test('Wrong database ownership marker rejected',()=>{let sh=databases.get(owner.spreadsheetId).getSheetByName('_Meta'),prior=sh.rows[1][1];sh.rows[1][1]='other@example.com';fail(()=>ctx.pdBootstrap(),/OWNER/);sh.rows[1][1]=prior});
test('Tampered committed snapshot fails closed',()=>{let sh=databases.get(owner.spreadsheetId).getSheetByName('_Snapshots');let i=sh.rows.findLastIndex(r=>r[0]==='DATA'),old=sh.rows[i][3];sh.rows[i][3]='B64:'+Buffer.from('{}').toString('base64url');fail(()=>ctx.pdBootstrap(),/INTEGRITY/);sh.rows[i][3]=old});
test('App lock contention is reported',()=>{locked=true;fail(()=>ctx.pdBootstrap(),/BUSY/);locked=false});
// Syntax checks do not constitute a browser test.
const html=fs.readFileSync(new URL('Index.html',root),'utf8'),client=html.match(/<script>([\s\S]*?)<\/script>/)[1];
test('Client JavaScript parses',()=>new vm.Script(client));
test('Manifest uses accessing-user identity and signed-in access',()=>{let m=JSON.parse(fs.readFileSync(new URL('appsscript.json',root),'utf8').replace(/^\uFEFF/,''));assert.equal(m.webapp.executeAs,'USER_ACCESSING');assert.equal(m.webapp.access,'ANYONE');assert.ok(!m.oauthScopes.some(x=>x.includes('gmail.read')))});
const report={testedAt:new Date().toISOString(),passed:passed.length,checks:passed,realGoogleDeploymentTested:false,actualGoogleEmailSent:false,browserInteractionTested:false,method:'Node VM with in-memory mocks of Google Sheets, identity, locks, properties and MailApp. No real email or Google account access.'};
fs.writeFileSync(new URL('TEST_RESULTS.json',root),JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));
