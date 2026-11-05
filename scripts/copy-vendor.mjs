import { mkdir,copyFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { dirname,resolve } from 'node:path';
const require=createRequire(import.meta.url);
const root=resolve(dirname(new URL(import.meta.url).pathname),'..');
await mkdir(resolve(root,'dist/vendor'),{recursive:true});
for(const [src,dest] of [['echarts/dist/echarts.min.js','echarts.min.js'],['pptxgenjs/dist/pptxgen.bundle.js','pptxgen.bundle.js']]) {
 let file;
 try {file=require.resolve(src)} catch {file=resolve(root,'node_modules',src)}
 await copyFile(file,resolve(root,'dist/vendor',dest));
}
for (const pkg of ['echarts','pptxgenjs']) {
 for (const name of ['LICENSE','LICENSE.txt']) {
  try {await copyFile(resolve(root,'node_modules',pkg,name),resolve(root,'dist/vendor',pkg+'-LICENSE.txt'));break}catch{}
 }
}
console.log('Pinned browser libraries copied to dist/vendor');
