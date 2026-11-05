const s=JSON.parse(require('fs').readFileSync(process.argv[2],'utf8'));
s.turns.forEach((t,i)=>console.log(i,JSON.stringify(t)));
for(const k of ['team1','team2'])console.log(k+'\n'+s[k].map((m,i)=>' Mon'+i+' '+m.species+' @'+m.item+' ['+m.ability+'] '+m.moves.join('/')).join('\n'));
