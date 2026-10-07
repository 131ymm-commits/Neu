// SELECT-01: сверка — промпты, собранные в JS-скрипте этапа, побайтно совпадают с промптами Python (prompts.eval_prompt).
//   node check_js.js run/<stage>.js run/<stage>_prompt_sha.json
const fs = require('fs'), crypto = require('crypto')
const src = fs.readFileSync(process.argv[2], 'utf8').split('\n')
const body = src.filter(l => /^const (TD|TPL|IDS|build) =/.test(l)).join('\n') + '\nreturn {build, IDS}'
const {build, IDS} = new Function(body)()
const want = JSON.parse(fs.readFileSync(process.argv[3], 'utf8')); let bad = 0
for (const id of IDS) if (crypto.createHash('sha256').update(build(id), 'utf8').digest('hex') !== want[id]) bad++
console.log(IDS.length, 'промптов, расхождений', bad)
