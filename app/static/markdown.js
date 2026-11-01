// 아주 작은 마크다운 변환기 (사내망에서도 동작하도록 외부 라이브러리 없이 작성)
// 지원: 코드 블록, 인라인 코드, 굵게, 기울임, 제목, 목록, 링크, 인용
(function () {
  function esc(s) {
    return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  function inline(s) {
    const codes = [];
    s = s.replace(/`([^`]+)`/g, (_, c) => { codes.push(c); return "\u0000" + (codes.length - 1) + "\u0000"; });
    s = esc(s)
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/(^|[^*])\*([^*\n]+)\*/g, "$1<em>$2</em>")
      .replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
    return s.replace(/\u0000(\d+)\u0000/g, (_, i) => "<code>" + esc(codes[+i]) + "</code>");
  }

  function render(src) {
    const out = [];
    const lines = src.replace(/\r\n/g, "\n").split("\n");
    let i = 0, list = null, para = [];

    const flushPara = () => { if (para.length) { out.push("<p>" + para.map(inline).join("<br>") + "</p>"); para = []; } };
    const closeList = () => { if (list) { out.push("</" + list + ">"); list = null; } };

    while (i < lines.length) {
      const line = lines[i];
      const fence = line.match(/^\s*```\s*([\w+#.-]*)/);
      if (fence) {
        flushPara(); closeList();
        const lang = fence[1] || "";
        const body = [];
        i++;
        while (i < lines.length && !/^\s*```\s*$/.test(lines[i])) body.push(lines[i++]);
        i++; // 닫는 ``` (스트리밍 중엔 없을 수 있음)
        out.push('<div class="codeblock"><div class="codehead"><span>' + esc(lang) +
          '</span><button class="copy-code" type="button">복사</button></div><pre><code>' +
          esc(body.join("\n")) + "</code></pre></div>");
        continue;
      }
      let m;
      if ((m = line.match(/^(#{1,4})\s+(.*)/))) {
        flushPara(); closeList();
        const n = Math.min(m[1].length + 2, 6);
        out.push(`<h${n}>${inline(m[2])}</h${n}>`);
      } else if ((m = line.match(/^\s*[-*]\s+(.*)/)) || (m = line.match(/^\s*\d+[.)]\s+(.*)/))) {
        flushPara();
        const type = /^\s*\d/.test(line) ? "ol" : "ul";
        if (list !== type) { closeList(); out.push("<" + type + ">"); list = type; }
        out.push("<li>" + inline(m[1]) + "</li>");
      } else if ((m = line.match(/^>\s?(.*)/))) {
        flushPara(); closeList();
        out.push("<blockquote>" + inline(m[1]) + "</blockquote>");
      } else if (!line.trim()) {
        flushPara(); closeList();
      } else {
        closeList();
        para.push(line);
      }
      i++;
    }
    flushPara(); closeList();
    return out.join("");
  }

  window.renderMarkdown = render;
})();
