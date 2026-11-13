'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const code=fs.readFileSync(require('node:path').join(__dirname,'../app.js'),'utf8');
const events=new Map();
function elem(id){return {id,innerHTML:'',textContent:'',value:'',dataset:{},classList:{toggle(){}},addEventListener(event,cb){events.set(id+':'+event,cb);},setAttribute(){},removeAttribute(){},scrollIntoView(){},click(){},appendChild(){},remove(){},style:{},focus(){}};}
const elems=new Map();
const get=id=>{if(!elems.has(id))elems.set(id,elem(id));return elems.get(id);};
const navs=['overview','queue','hosts','cycle','evidence','timeline','safety'].map(v=>{const x=elem('nav-'+v);x.dataset.view=v;return x;});
const doc={querySelector:get,querySelectorAll(sel){if(sel==='.navitem')return navs;return[];},createElement:elem,body:{appendChild(){}}};
const local=new Map();
const c={document:doc,window:{},localStorage:{getItem:k=>local.get(k)||null,setItem:(k,v)=>local.set(k,v)},Intl,Date,Math,JSON,Number,String,Array,Set,RegExp,Object,URL,Blob,FormData,console,setTimeout(){},clearTimeout(){}};
vm.createContext(c);vm.runInContext(code,c);
let initial=get('#screen').innerHTML;
assert.match(initial,/Ciclo operacional/);
assert.match(initial,/0\s*\/\s*10/);
assert.match(initial,/DESKTOP-PDQK954/);
assert.match(initial,/DESKTOP-RP23OGS/);
assert.match(initial,/Noteri/);
assert.equal(c.window.ReqSysPainelTeste.accepted(),0);
assert.equal(c.window.ReqSysPainelTeste.total(),10);
assert.equal(c.window.ReqSysPainelTeste.shaValid('a'.repeat(40)),true);
assert.equal(c.window.ReqSysPainelTeste.shaValid('a'.repeat(39)),false);
assert.equal(c.window.ReqSysPainelTeste.hostReadyVerified(),0);
for(const nav of navs){events.get(nav.id+':click')();assert.ok(get('#screen').innerHTML.length>500,nav.id);}
assert.match(get('#screen').innerHTML,/Operational Rules v1\.6\.21/);
console.log('12 verificações lógicas/estáticas JS aprovadas; E2E de navegador não substituído.');
