/* Authoring template for wiki/wiki-share-poster.png, not a browser runtime dependency.
 * Render create() with the exported site's original artwork and a native canvas adapter.
 * Re-decode the final PNG QR whenever regenerating; it must match website exactly.
 * Original character artwork is contained, never cropped.
 */
(() => {
  'use strict';
  const website = 'https://wf-mod-wiki.pages.dev/';
  const characters = Object.freeze([
    {name:'校园希尔媞 · 觉醒前', url:'media/f72484fde5159aa02141d3fd71b8d232466fe943ee57403dc051f150fb1f5d31.webp'},
    {name:'情风龙 · 觉醒后', url:'media/0c412e85c0b325eabb2c11dcd124415ab041c003577163bd17316706950d2b36.webp'},
    {name:'冰雪罗尔夫 · 觉醒前', url:'media/3524abd20a2c2b2f01f622bd240e8e668d29221ccd171045b6d0770295def201.webp'},
  ].map(Object.freeze));
  // ReportLab QR encoder, version 3 / M, exact website above; four-module quiet zone below.
  const qr = [
    '11111110011011110011101111111',
    '10000010011011111100101000001',
    '10111010111001010000001011101',
    '10111010111110110100001011101',
    '10111010101010011011101011101',
    '10000010110010000000001000001',
    '11111110101010101010101111111',
    '00000000101000101000000000000',
    '10111110000010001100101111100',
    '11110100111101110001111110001',
    '00100010101111111110001110000',
    '10001101000011010001101101010',
    '01101111101100110111000001100',
    '00100100100110011111011110001',
    '10111111001010000100100111100',
    '10110001110100101010010100010',
    '00101011110000001101010001100',
    '11101100100001110011111010101',
    '10101010010101111000101000100',
    '10100000100111010011000110010',
    '10111011101110110101111110111',
    '00000000110100011010100011111',
    '11111110001010000001101011100',
    '10000010100110101001100010011',
    '10111010100010000100111110101',
    '10111010101101110001000001100',
    '10111010100010111100101111110',
    '10000010010001101010100101010',
    '11111110100101000111001111100',
  ];
  function load(value) {
    return new Promise((resolve, reject) => {
      let url;
      try {
        const base = new URL(document.baseURI); url = new URL(value, base);
        if (typeof value !== 'string' || !value || url.origin !== base.origin || !['https:','http:','file:'].includes(url.protocol)) throw Error();
      } catch {reject(new Error('宣传图素材地址无效。')); return;}
      const image = new Image(); image.decoding = 'async';
      if (url.protocol !== 'file:') image.crossOrigin = 'anonymous';
      const timer = setTimeout(() => finish(new Error('宣传图素材加载超时，请重试。')), 15000);
      function finish(error) {
        clearTimeout(timer); image.onload = image.onerror = null;
        if (error) reject(error); else resolve(image);
      }
      image.onload = () => finish(image.naturalWidth && image.naturalHeight ? null : new Error('宣传图素材为空。'));
      image.onerror = () => finish(new Error('宣传图素材加载失败，请重试。'));
      image.src = url.href;
    });
  }
  async function create({characters: selected = characters, logoUrl = 'brand-logo.png'} = {}) {
    if (!Array.isArray(selected) || selected.length < 3 || selected.length > 4 || selected.some(item => !item || typeof item.name !== 'string' || !item.name.trim()))
      throw new Error('宣传图需要 3–4 位角色及其名称。');
    const rows = selected.map(item => ({name:item.name.trim().replace(/\s+/g, ' '), url:item.url}));
    const [logo, ...images] = await Promise.all([load(logoUrl), ...rows.map(item => load(item.url))]);
    const canvas = document.createElement('canvas'); canvas.width = 960; canvas.height = 1280;
    const ctx = canvas.getContext('2d'); if (!ctx) throw new Error('浏览器暂不支持生成宣传图。');
    ctx.imageSmoothingEnabled = true; ctx.imageSmoothingQuality = 'high';
    function rect(x, y, w, h, radius, color) {
      ctx.fillStyle = color; ctx.beginPath(); ctx.roundRect(x, y, w, h, radius); ctx.fill();
    }
    function text(value, x, y, size, color = '#203d3a', weight = 400, width = 832) {
      const font = () => {ctx.font = `${weight} ${size}px "Microsoft YaHei", "PingFang SC", sans-serif`;};
      font(); while (size > 12 && ctx.measureText(value).width > width) {size--; font();}
      ctx.fillStyle = color; ctx.fillText(value, x, y, width);
    }
    function contain(image, x, y, width, height) {
      const scale = Math.min(width / image.naturalWidth, height / image.naturalHeight);
      const w = image.naturalWidth * scale, h = image.naturalHeight * scale;
      ctx.drawImage(image, x + (width - w) / 2, y + (height - h) / 2, w, h);
    }
    ctx.fillStyle = '#f4f7f2'; ctx.fillRect(0, 0, 960, 1280);
    rect(64, 60, 64, 64, 16, '#ffffff'); contain(logo, 72, 68, 48, 48);
    text('PARADOX  /  WORLD FLIPPER', 146, 88, 17, '#8c7747', 600);
    text('与你一起，发现弹射世界', 146, 116, 18, '#66817b');
    text('星见图鉴', 60, 222, 82, '#164f48', 700);
    text('世界弹射物语 · 非官方 Wiki', 67, 266, 25, '#66817b');
    rect(64, 300, 72, 5, 2, '#c3a35d'); rect(150, 302, 746, 1, 0, '#d5dfd6');
    text('你的冒险，从这里继续。', 64, 359, 31, '#203d3a', 600);
    ['角色图鉴','队伍编成','配队大全','副本攻略'].forEach((label, i) => {
      rect(64 + i * 212, 388, 196, 46, 12, i % 2 ? '#eee9dc' : '#e0eee8');
      text(label, 110 + i * 212, 419, 23, '#3b645c', 500, 150);
    });
    const gap = 14, width = (832 - gap * (rows.length - 1)) / rows.length;
    rows.forEach((item, index) => {
      const x = 64 + index * (width + gap);
      rect(x, 466, width, 475, 20, '#ffffff');
      rect(x + 12, 478, width - 24, 391, 14, ['#edf5ef','#e5f2ef','#f0f0eb','#edf0f5'][index]);
      contain(images[index], x + 16, 492, width - 32, 363);
      const [name, form] = item.name.split(' · ');
      text(name, x + 18, 900, 24, '#294e47', 600, width - 36);
      if (form) text(form, x + 18, 925, 16, '#7c8b80', 400, width - 36);
    });
    text('扫码打开星见图鉴', 64, 1037, 32, '#164f48', 600);
    text('查角色 · 找配队 · 看攻略', 64, 1081, 23, '#66817b', 400, 560);
    text(website, 64, 1158, 26, '#3a655c', 500, 570);
    rect(674, 982, 222, 222, 0, '#ffffff'); ctx.fillStyle = '#173f39';
    qr.forEach((row, y) => [...row].forEach((bit, x) => {if (bit === '1') ctx.fillRect(698 + x * 6, 1006 + y * 6, 6, 6);}));
    text('非官方玩家资料站  ·  BY PARADOX', 64, 1236, 17, '#899488');
    return new Promise((resolve, reject) => {
      try {canvas.toBlob(blob => blob?.size ? resolve(blob) : reject(new Error('宣传图导出失败，请重试。')), 'image/png');}
      catch {reject(new Error('宣传图导出失败，请确认图片可从本站正常加载。'));}
    });
  }
  window.WFWikiSharePoster = Object.freeze({create, characters, website});
})();
