#!/usr/bin/env node
'use strict';
const path = require('path');
const s = require(path.join(process.env.USERPROFILE, '.claude', 'settings.json'));
for (const [evt, entries] of Object.entries(s.hooks || {})) {
  const cmds = entries.map(e => e.hooks.map(h => h.command)).flat();
  const seen = {};
  cmds.forEach(c => { seen[c] = (seen[c] || 0) + 1; });
  const dups = Object.entries(seen).filter(([, v]) => v > 1);
  if (dups.length) {
    console.log(evt + ':');
    dups.forEach(([cmd, count]) => {
      const basename = path.basename(cmd.split(' ').pop().replace(/"/g, ''));
      console.log('  DUP x' + count + ': ' + basename);
    });
  }
}
