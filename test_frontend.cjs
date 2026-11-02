const fs=require('fs'),vm=require('vm'),assert=require('assert');
const fixture=JSON.parse(fs.readFileSync('qa/fixture.json','utf8'));
const elements=new Map();
const element=()=>({innerHTML:'',textContent:'',content:'test-token',value:'',style:{},showModal(){},close(){}});
const document={querySelector(s){if(!elements.has(s))elements.set(s,element());return elements.get(s)},querySelectorAll(){return []},addEventListener(){}};
const context=vm.createContext({document,console,Date,Number,String,JSON,Array,Object,Map,Set,Math,setTimeout,clearTimeout,fixture,localStorage:{getItem(){return null},setItem(){}},fetch:()=>Promise.reject(Error('No network in unit test'))});
let source=fs.readFileSync('static/app.js','utf8');source=source.replace('loadCompanies().catch(e=>toast(e.message,true));','');vm.runInContext(source,context);
vm.runInContext(`S=fixture.state;R=fixture.report;companies=fixture.companies;cid=S.company.id;dates={start:'2026-01-01',end:'2026-10-24'};`,context);
let count=0;
for(const view of ['Overview','Transactions','Contacts & items','Chart of accounts','Fixed assets','Bank reconciliation','Reports','Group overview','Controls & backup']){
 vm.runInContext(`page=${JSON.stringify(view)};render()`,context);assert(document.querySelector('#content').innerHTML.length>100,view);count++;
}
for(const name of ['Trial balance','Profit & loss','Balance sheet','Cash flow','General ledger','Receivables & payables','VAT summary']){
 vm.runInContext(`page='Reports';report=${JSON.stringify(name)};render()`,context);assert(document.querySelector('#content').innerHTML.includes(name));count++;
}
vm.runInContext("createCompany();addMaster('contacts');addMaster('accounts');addMaster('items');addAsset()",context);
assert(vm.runInContext("esc('<script>')",context)==='&lt;script&gt;');
console.log(count+' view/report render checks + 5 form renders + escaping check passed. (Unit rendering; not a browser test.)');
