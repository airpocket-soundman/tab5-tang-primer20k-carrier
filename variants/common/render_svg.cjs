const sharp = require('C:/Users/yamashita_y00031/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/sharp');
sharp(process.argv[2], {density: 150}).flatten({background:'#ffffff'}).resize({width:1500}).png().toFile(process.argv[3]).then(()=>console.log(process.argv[3]));
