const sharp = require('C:/Users/yamashita_y00031/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/sharp');
sharp(process.argv[2],{density:250}).resize({width:1600}).flatten({background:'#ffffff'}).png().toFile(process.argv[3]);
