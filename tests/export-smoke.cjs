const fs=require('node:fs'), vm=require('node:vm'), path=require('node:path'), assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const RealPptx=require('pptxgenjs');
const os=require('node:os'),cp=require('node:child_process');
const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'macro-lens-export-test-'));
const doc={documentElement:{},querySelector(){return null},querySelectorAll(){return []}};
class Pptx extends RealPptx {async writeFile(args){args.fileName=path.join(tmp,args.fileName);return super.writeFile(args)}}
const ctx={console,document:doc,location:{search:''},localStorage:{getItem(){return null},setItem(){}},URLSearchParams,PptxGenJS:Pptx,setTimeout,Blob,URL};
vm.createContext(ctx);vm.runInContext(fs.readFileSync(root+'/dist/i18n.js','utf8'),ctx);
let app=fs.readFileSync(root+'/dist/app.js','utf8');app=app.slice(0,app.indexOf('function changeLanguage'));vm.runInContext(app,ctx);vm.runInContext('DATA='+fs.readFileSync(root+'/dist/data/macro.json','utf8'),ctx);
(async()=>{
 for(const lang of ['CH','EN','JP']){
  vm.runInContext(`I18N.set('${lang}')`,ctx);
  const metadata=vm.runInContext('Object.keys(DEF).filter(valid).map(key=>({raw:rawSpec(key),localized:getSpec(key)}))',ctx);
  for(const {raw,localized} of metadata){
   assert.equal(JSON.stringify(raw.series.map(v=>v.values)),JSON.stringify(localized.series.map(v=>v.values)),'Language must never change numeric observations');
   if(lang==='EN')for(const field of ['title','unit','source','note'])assert.ok(!/[\u3400-\u9fff]/.test(localized[field]||''),'Untranslated chart metadata: '+localized[field]);
  }
  for(const bw of [false,true]){
   vm.runInContext(`blackWhite=${bw}`,ctx);
   await vm.runInContext('exportPpt(Object.keys(DEF).filter(valid).map(key=>({key,period:DEF[key].period})))',ctx);
   console.log('EXPORTED',lang,bw?'BW':'COLOR');
  }
 }
 cp.execFileSync('python',['-c',`
import zipfile,glob,re,sys,xml.etree.ElementTree as ET
files=glob.glob(sys.argv[1]+'/*.pptx');assert len(files)==6
for f in files:
 z=zipfile.ZipFile(f)
 charts=[n for n in z.namelist() if re.fullmatch(r'ppt/charts/chart\\d+.xml',n)]
 slides=[n for n in z.namelist() if re.fullmatch(r'ppt/slides/slide\\d+.xml',n)]
 books=[n for n in z.namelist() if n.startswith('ppt/embeddings/') and n.endswith('.xlsx')]
 assert len(charts)==len(slides)==len(books)==22,(f,len(charts),len(slides),len(books))
 for n in charts+slides:
  txt=z.read(n).decode()
  if '_BW' in f:
   for c in re.findall(r'<a:srgbClr val="([A-Fa-f0-9]{6})"',txt):
    assert c[:2].lower()==c[2:4].lower()==c[4:].lower(),(f,n,c)
  if '_EN_' in f:
   for e in ET.fromstring(txt).iter():
    if e.tag.endswith(('}t','}v')) and e.text and not e.text.startswith('http'):
     assert not re.search(r'[\\u3400-\\u9fff]',e.text),(f,n,e.text)
print('Passed: 6 localized decks, 132 editable charts/workbooks, grayscale-only BW output')
`,tmp],{stdio:'inherit'});
 fs.rmSync(tmp,{recursive:true,force:true});
})().catch(e=>{console.error(e);process.exit(1)});
