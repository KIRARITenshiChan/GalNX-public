const fs = require('fs');
const src = fs.readFileSync('E:/galnx-build/nvdec/research/envideo/test/decode.cpp', 'utf8');
function grab(name) {
  const re = new RegExp('std::uint8_t\\s+' + name + '\\[\\]\\s*=\\s*\\{([\\s\\S]*?)\\n\\};');
  const m = src.match(re);
  if (!m) throw new Error('not found: ' + name);
  return m[1];
}
const lines = [];
lines.push('/* Auto-generated from averne/envideo test/decode.cpp (GPLv2+).');
lines.push(' * MPEG2 128x128 reference vectors for GalNX probe5. Do not edit. */');
lines.push('#pragma once');
lines.push('#include <stdint.h>');
lines.push('');
for (const name of ['pic_setup_bin', 'bitstream_bin', 'slice_offsets_bin']) {
  const body = grab(name).split('\n').map(s => s.trim()).join(' ');
  const count = (body.match(/0x[0-9a-fA-F]+|\b\d+\b/g) || []).length;
  lines.push('static const uint8_t ' + name + '[] = {' + body + '};');
  lines.push('/* entries: ' + count + ' */');
  lines.push('');
}
fs.writeFileSync('E:/galnx-build/nvdec/probe5/include/ref_mpeg2_data.h', lines.join('\n'));
console.log('wrote header', lines.join('\n').length);
