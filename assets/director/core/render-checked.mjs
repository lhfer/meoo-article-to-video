/** Checked render entry. Stable official @remotion/bundler + @remotion/renderer APIs.
 * node core/render-checked.mjs work/render-config.json
 * Missing browser frame receipts are a hard failure, not a successful unchecked render.
 */
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {createReadStream} from 'node:fs';
import path from 'node:path';
import {createHash,randomUUID} from 'node:crypto';
import {bundle} from '@remotion/bundler';
import {selectComposition,renderMedia} from '@remotion/renderer';
import {collectLayoutReceipt,verifyCoverage} from './layout-receipts.mjs';
async function sha256(file){const h=createHash('sha256');for await(const chunk of createReadStream(file))h.update(chunk);return h.digest('hex');}
const configPath=process.argv[2];if(!configPath)throw new Error('Pass render config JSON');
const cfg=JSON.parse(await readFile(configPath,'utf8'));
if(!['3x4','9x16','16x9'].includes(cfg.format)||!Number.isInteger(cfg.frames)||cfg.frames<1||!(cfg.scale>0&&cfg.scale<=2))throw new Error('Invalid render config');
const token=randomUUID(),seen=new Set();
const inputProps={format:cfg.format,noMusic:!!cfg.noMusic,strictLayout:true,layoutReceiptToken:token};
const browserExecutable=cfg.browserExecutable||process.env.CHROMIUM_PATH||undefined;
const chromiumOptions=cfg.gl?{gl:cfg.gl}:undefined;
await mkdir(path.dirname(cfg.output),{recursive:true});
const serveUrl=await bundle({entryPoint:path.resolve('src/index.ts'),outDir:path.resolve('work/remotion-bundle'),publicDir:path.resolve('public')});
const composition=await selectComposition({serveUrl,id:`Film-${cfg.format}`,inputProps,browserExecutable,chromiumOptions});
if(cfg.frames>composition.durationInFrames)throw new Error('Requested frame range exceeds composition');
await renderMedia({serveUrl,composition,codec:'h264',outputLocation:cfg.output,inputProps,frameRange:[0,cfg.frames-1],scale:cfg.scale,crf:18,
 imageFormat:cfg.gl?'png':'jpeg',browserExecutable,chromiumOptions,logLevel:'warn',
 ...(cfg.concurrency?{concurrency:cfg.concurrency}:{}),
 onBrowserLog:(log)=>{if(!collectLayoutReceipt(log,token,cfg.format,seen)&&['error','warning','warn'].includes(log.type))console.error(log.text);}
});
const result={...verifyCoverage(seen,0,cfg.frames-1),format:cfg.format,inputSha256:await sha256(cfg.output),receiptToken:token};
const receiptPath=cfg.output.replace(/\.[^.]+$/,'.layout.json');
await writeFile(receiptPath,JSON.stringify(result,null,2)+'\n');
console.log(JSON.stringify({output:cfg.output,layoutReceipt:receiptPath,checkedFrames:result.checkedFrames}));
