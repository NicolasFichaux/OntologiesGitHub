const {JSDOM}=require('jsdom'); const fs=require('fs');
const html=fs.readFileSync('/mnt/user-data/outputs/earth-data-navigator.html','utf8');
let prompts=[];
const dom=new JSDOM(html,{runScripts:'dangerously',pretendToBeVisual:true,beforeParse(w){
  w.Element.prototype.scrollIntoView=()=>{}; w.scrollTo=()=>{};
  w.addEventListener('error',e=>{console.error('PAGE ERROR',e.message)});
  const sample=async()=>({text:''}); sample.json=async(p,o)=>{prompts.push(p);
    if(/e-shape pilot services/.test(p)) return {overall:"One pilot fits rooftop solar.",matches:[{code:"S3P2",fit:"strong",why:"rooftop irradiance",gaps:"check DSM for Marseille"},{code:"S9P9",fit:"strong",why:"x",gaps:"y"},{code:"s2-p1",fit:"odd",why:"w",gaps:""}]};
    return {understanding:"Solar in Marseille",candidates:[{service:"Map & monitor solar energy (solar farms)",confidence:0.9,reason:"solar"}],questions:[],params:{place:"Marseille",bbox:[5.2,43.2,5.6,43.4],start:null,end:null,scale:"local",wants:"either"}};};
  w.claude={use:async n=> n==='sample'?sample: n==='downloads'?{save:async()=>{}}:null};
}});
const d=dom.window.document; const wait=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{
  await wait(100);
  d.getElementById('need').value='Rooftop solar in Marseille'; d.getElementById('go').click(); await wait(150);
  console.log('s3',!d.getElementById('s3').hidden,'s4',!d.getElementById('s4').hidden,'calls',prompts.length,'pilot prompt bytes',prompts[1].length);
  const pc=[...d.querySelectorAll('#pilots .svc')]; console.log('pilot cards',pc.length, pc.map(c=>c.querySelector('h3').textContent.slice(0,40)+' | '+c.querySelector('.badge').textContent));
  console.log('overall:',d.getElementById('pstatus').textContent,'| dots',pc[0].querySelectorAll('.dot').length,'| adapt',pc[0].querySelectorAll('.tag.adapt').length,'| contacts',pc[0].querySelectorAll('ul.res a').length);
  d.getElementById('reset').click(); await wait(20);
  console.log('after reset: need="'+d.getElementById('need').value+'" s2',d.getElementById('s2').hidden,'s3',d.getElementById('s3').hidden,'s4',d.getElementById('s4').hidden,'results',d.getElementById('results').children.length,'pilots',d.getElementById('pilots').children.length);
  d.getElementById('optPilots').checked=false; d.getElementById('manualGo').click(); await wait(100);
  console.log('manual without option: s3',!d.getElementById('s3').hidden,'s4 hidden',d.getElementById('s4').hidden,'calls',prompts.length);
})().catch(e=>{console.error('ERR',e);process.exit(1)});
