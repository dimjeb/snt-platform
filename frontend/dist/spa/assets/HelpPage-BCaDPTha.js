import{c as e,d as t,j as n,m as r,s as i}from"./runtime-core.esm-bundler-CsWxG9hj.js";import{t as a}from"./QBtn-q7k-l82W.js";import{B as o,K as s,W as c}from"./index-C0C9y32N.js";import{t as l}from"./QSpace-BIW09l6H.js";function u(e){"@babel/helpers - typeof";return u=typeof Symbol==`function`&&typeof Symbol.iterator==`symbol`?function(e){return typeof e}:function(e){return e&&typeof Symbol==`function`&&e.constructor===Symbol&&e!==Symbol.prototype?`symbol`:typeof e},u(e)}function d(e,t){if(u(e)!=`object`||!e)return e;var n=e[Symbol.toPrimitive];if(n!==void 0){var r=n.call(e,t||`default`);if(u(r)!=`object`)return r;throw TypeError(`@@toPrimitive must return a primitive value.`)}return(t===`string`?String:Number)(e)}function f(e){var t=d(e,`string`);return u(t)==`symbol`?t:t+``}function p(e,t,n){return(t=f(t))in e?Object.defineProperty(e,t,{value:n,enumerable:!0,configurable:!0,writable:!0}):e[t]=n,e}var m;function h(){return{async:!1,breaks:!1,extensions:null,gfm:!0,hooks:null,pedantic:!1,renderer:null,silent:!1,tokenizer:null,walkTokens:null}}var g=h();function _(e){g=e}var v={exec:()=>null};function y(e){let t=[];return n=>{let r=Math.max(0,Math.min(3,n-1)),i=t[r];return i||(i=e(r),t[r]=i),i}}function b(e,t=``){let n=typeof e==`string`?e:e.source,r={replace:(e,t)=>{let i=typeof t==`string`?t:t.source;return i=i.replace(x.caret,`$1`),n=n.replace(e,i),r},getRegex:()=>new RegExp(n,t)};return r}var ee=((e=``)=>{try{return!!RegExp(`(?<=1)(?<!1)`+e)}catch{return!1}})(),x={codeRemoveIndent:/^(?: {0,3}\t| {1,4})/gm,outputLinkReplace:/\\([\[\]])/g,indentCodeCompensation:/^(\s+)(?:```)/,beginningSpace:/^\s+/,endingHash:/#$/,startingSpaceChar:/^ /,endingSpaceChar:/ $/,endingSpaceTabChar:/[ \t]$/,nonSpaceChar:/[^ ]/,newLineCharGlobal:/\n/g,tabCharGlobal:/\t/g,leadingSpaceTab:/^[ \t]+/,multipleSpaceGlobal:/\s+/g,blankLine:/^[ \t]*$/,doubleBlankLine:/\n[ \t]*\n[ \t]*$/,blockquoteStart:/^ {0,3}>/,blockquoteSetextReplace:/\n {0,3}((?:=+|-+) *)(?=\n|$)/g,blockquoteSetextReplace2:/^ {0,3}>[ \t]?/gm,listReplaceNesting:/^ {1,4}(?=( {4})*[^ ])/g,listIsTask:/^\[[ xX]\] +\S/,listReplaceTask:/^\[[ xX]\] +/,listTaskCheckbox:/\[[ xX]\]/,anyLine:/\n.*\n/,hrefBrackets:/^<(.*)>$/,tableDelimiter:/[:|]/,tableAlignChars:/^\||\| *$/g,tableRowBlankLine:/\n[ \t]*$/,tableAlignRight:/^ *-+: *$/,tableAlignCenter:/^ *:-+: *$/,tableAlignLeft:/^ *:-+ *$/,startATag:/^<a /i,endATag:/^<\/a>/i,startPreScriptTag:/^<(pre|code|kbd|script)(\s|>)/i,endPreScriptTag:/^<\/(pre|code|kbd|script)(\s|>)/i,startAngleBracket:/^</,endAngleBracket:/>$/,pedanticHrefTitle:/^([^'"]*[^\s])\s+(['"])(.*)\2/,unicodeAlphaNumeric:/[\p{L}\p{N}]/u,numericCharacterReference:/&#(?:(\d{1,7})|[Xx]([A-Fa-f0-9]{1,6}));/g,escapeTest:/[&<>"']/,escapeReplace:/[&<>"']/g,escapeTestNoEncode:/[<>"']|&(?!(#\d{1,7}|#[Xx][a-fA-F0-9]{1,6}|\w+);)/,escapeReplaceNoEncode:/[<>"']|&(?!(#\d{1,7}|#[Xx][a-fA-F0-9]{1,6}|\w+);)/g,caret:/(^|[^\[])\^/g,percentDecode:/%25/g,findPipe:/\|/g,splitPipe:/ \|/,slashPipe:/\\\|/g,carriageReturn:/\r\n|\r/g,spaceLine:/^ +$/gm,notSpaceStart:/^\S*/,endingNewline:/\n$/,listItemRegex:e=>RegExp(`^( {0,3}${e})((?:[	 ][^\\n]*)?(?:\\n|$))`),nextBulletRegex:y(e=>RegExp(`^ {0,${e}}(?:[*+-]|\\d{1,9}[.)])((?:[ 	][^\\n]*)?(?:\\n|$))`)),hrRegex:y(e=>RegExp(`^ {0,${e}}((?:-[ 	]*){3,}|(?:_[ 	]*){3,}|(?:\\*[ 	]*){3,})(?:\\n+|$)`)),fencesBeginRegex:y(e=>RegExp(`^ {0,${e}}(?:\`\`\`|~~~)`)),headingBeginRegex:y(e=>RegExp(`^ {0,${e}}#`)),htmlBeginRegex:y(e=>RegExp(`^ {0,${e}}(?:</?(?:${E})(?: +|$|/?>)|<(?:script|pre|style|textarea|!--))`,`i`)),blockquoteBeginRegex:y(e=>RegExp(`^ {0,${e}}>`))},te=/^(?:[ \t]*(?:\n|$))+/,ne=/^((?: {4}| {0,3}\t)[^\n]+(?:\n(?:[ \t]*(?:\n|$))*)?)+/,re=/^ {0,3}(`{3,}(?=[^`\n]*(?:\n|$))|~{3,})([^\n]*)(?:\n|$)(?:|([\s\S]*?)(?:\n|$))(?: {0,3}\1[~`]* *(?=\n|$)|$)/,S=/^ {0,3}((?:-[\t ]*){3,}|(?:_[ \t]*){3,}|(?:\*[ \t]*){3,})(?:\n+|$)/,ie=/^ {0,3}(#{1,6})(?=\s|$)(.*)(?:\n+|$)/,C=/ {0,3}(?:[*+-]|\d{1,9}[.)])/,ae=/^(?!bull |blockCode|fences|blockquote|heading|html|table)((?:.|\n(?!\s*?\n|bull |fences|blockquote|heading|hr|html|table))+?)\n {0,3}(=+|-+) *(?:\n+|$)/,oe=b(ae).replace(/bull/g,C).replace(/blockCode/g,/(?: {4}| {0,3}\t)/).replace(/fences/g,/ {0,3}(?:`{3,}|~{3,})/).replace(/blockquote/g,/ {0,3}>/).replace(/heading/g,/ {0,3}#{1,6}(?:\s|$)/).replace(/hr/g,/ {0,3}(?:(?:-[\t ]*){3,}|(?:_[ \t]*){3,}|(?:\*[ \t]*){3,})(?:\n+|$)/).replace(/html/g,/ {0,3}<[^\n>]+>\n/).replace(/\|table/g,``).getRegex(),se=b(ae).replace(/bull/g,C).replace(/blockCode/g,/(?: {4}| {0,3}\t)/).replace(/fences/g,/ {0,3}(?:`{3,}|~{3,})/).replace(/blockquote/g,/ {0,3}>/).replace(/heading/g,/ {0,3}#{1,6}(?:\s|$)/).replace(/hr/g,/ {0,3}(?:(?:-[\t ]*){3,}|(?:_[ \t]*){3,}|(?:\*[ \t]*){3,})(?:\n+|$)/).replace(/html/g,/ {0,3}<[^\n>]+>\n/).replace(/table/g,/ {0,3}\|?(?:[:\- ]*\|)+[\:\- ]*\n/).getRegex(),w=/^([^\n]+(?:\n(?!hr|heading|lheading|blockquote|fences|list|html|table|[ \t]+\n)[^\n]+)*)/,ce=/^[^\n]+/,T=/(?!\s*\])(?:\\[\s\S]|[^\[\]\\])+/,le=b(/^ {0,3}\[(label)\]: *(?:\n[ \t]*)?([^<\s][^\s]*|<.*?>)(?:(?: +(?:\n[ \t]*)?| *\n[ \t]*)(title))? *(?:\n+|$)/).replace(`label`,T).replace(`title`,/(?:"(?:\\"?|[^"\\])*"|'[^'\n]*(?:\n[^'\n]+)*\n?'|\([^()]*\))/).getRegex(),ue=b(/^(bull)([ \t][^\n]*?)?(?:\n|$)/).replace(/bull/g,C).getRegex(),E=`address|article|aside|base|basefont|blockquote|body|caption|center|col|colgroup|dd|details|dialog|dir|div|dl|dt|fieldset|figcaption|figure|footer|form|frame|frameset|h[1-6]|head|header|hr|html|iframe|legend|li|link|main|menu|menuitem|meta|nav|noframes|ol|optgroup|option|p|param|search|section|summary|table|tbody|td|tfoot|th|thead|title|tr|track|ul`,D=/<!--(?:-?>|[\s\S]*?(?:-->|$))/,de=b(`^ {0,3}(?:<(script|pre|style|textarea)[\\s>][\\s\\S]*?(?:</\\1>[^\\n]*\\n*|$)|comment[^\\n]*(\\n+|$)|<\\?[\\s\\S]*?(?:\\?>[^\\n]*\\n*|$)|<![A-Z][\\s\\S]*?(?:>[^\\n]*\\n*|$)|<!\\[CDATA\\[[\\s\\S]*?(?:\\]\\]>[^\\n]*\\n*|$)|</?(tag)(?: +|\\n|/?>)[\\s\\S]*?(?:(?:\\n[ 	]*)+\\n|$)|<(?!script|pre|style|textarea)([a-z][a-z0-9-]*)(?:attribute)*? */?>(?=[ \\t]*(?:\\n|$))[\\s\\S]*?(?:(?:\\n[ 	]*)+\\n|$)|</(?!script|pre|style|textarea)[a-z][a-z0-9-]*\\s*>(?=[ \\t]*(?:\\n|$))[\\s\\S]*?(?:(?:\\n[ 	]*)+\\n|$))`,`i`).replace(`comment`,D).replace(`tag`,E).replace(`attribute`,/ +[a-zA-Z:_][\w.:-]*(?: *= *"[^"\n]*"| *= *'[^'\n]*'| *= *[^\s"'=<>`]+)?/).getRegex(),O=e=>b(w).replace(`hr`,S).replace(`heading`,` {0,3}#{1,6}(?:\\s|$)`).replace(`|lheading`,``).replace(`|table`,``).replace(`blockquote`,` {0,3}>`).replace(`fences`," {0,3}(?:`{3,}(?=[^`\\n]*(?:\\n|$))|~~~)[^\\n]*(?:\\n|$)").replace(`list`,e).replace(`html`,`</?(?:tag)(?: +|\\n|/?>)|<(?:script|pre|style|textarea|!--)`).replace(`tag`,E).getRegex(),fe=O(/ {0,3}(?:[*+-]|1[.)])[ \t]+[^ \t\n]/),pe=O(/ {0,3}(?:[*+-]|\d{1,9}[.)])(?:[ \t]|\n|$)/),k={blockquote:b(/^( {0,3}> ?(paragraph|[^\n]*)(?:\n|$))+/).replace(`paragraph`,pe).getRegex(),code:ne,def:le,fences:re,heading:ie,hr:S,html:de,lheading:oe,list:ue,newline:te,paragraph:fe,table:v,text:ce},A=b(`^ *([^\\n ].*)\\n {0,3}((?:\\| *)?:?-+:? *(?:\\| *:?-+:? *)*(?:\\| *)?)(?:\\n((?:(?! *\\n|hr|heading|blockquote|code|fences|list|html).*(?:\\n|$))*)\\n*|$)`).replace(`hr`,S).replace(`heading`,` {0,3}#{1,6}(?:\\s|$)`).replace(`blockquote`,` {0,3}>`).replace(`code`,`(?: {4}| {0,3}	)[^\\n]`).replace(`fences`," {0,3}(?:`{3,}(?=[^`\\n]*(?:\\n|$))|~~~)[^\\n]*(?:\\n|$)").replace(`list`,` {0,3}(?:[*+-]|1[.)])[ \\t]`).replace(`html`,`</?(?:tag)(?: +|\\n|/?>)|<(?:script|pre|style|textarea|!--)`).replace(`tag`,E).getRegex(),me={...k,lheading:se,table:A,paragraph:b(w).replace(`hr`,S).replace(`heading`,` {0,3}#{1,6}(?:\\s|$)`).replace(`|lheading`,``).replace(`table`,A).replace(`blockquote`,` {0,3}>`).replace(`fences`," {0,3}(?:`{3,}(?=[^`\\n]*(?:\\n|$))|~~~)[^\\n]*(?:\\n|$)").replace(`list`,` {0,3}(?:[*+-]|1[.)])[ \\t]+[^ \\t\\n]`).replace(`html`,`</?(?:tag)(?: +|\\n|/?>)|<(?:script|pre|style|textarea|!--)`).replace(`tag`,E).getRegex()},he={...k,html:b(`^ *(?:comment *(?:\\n|\\s*$)|<(tag)[\\s\\S]+?</\\1> *(?:\\n{2,}|\\s*$)|<tag(?:"[^"]*"|'[^']*'|\\s[^'"/>\\s]*)*?/?> *(?:\\n{2,}|\\s*$))`).replace(`comment`,D).replace(/tag/g,`(?!(?:a|em|strong|small|s|cite|q|dfn|abbr|data|time|code|var|samp|kbd|sub|sup|i|b|u|mark|ruby|rt|rp|bdi|bdo|span|br|wbr|ins|del|img)\\b)\\w+(?!:|[^\\w\\s@]*@)\\b`).getRegex(),def:/^ *\[([^\]]+)\]: *<?([^\s>]+)>?(?: +(["(][^\n]+[")]))? *(?:\n+|$)/,heading:/^(#{1,6})(.*)(?:\n+|$)/,fences:v,lheading:/^(.+?)\n {0,3}(=+|-+) *(?:\n+|$)/,paragraph:b(w).replace(`hr`,S).replace(`heading`,` *#{1,6} *[^
]`).replace(`lheading`,oe).replace(`|table`,``).replace(`blockquote`,` {0,3}>`).replace(`|fences`,``).replace(`|list`,``).replace(`|html`,``).replace(`|tag`,``).getRegex()},ge=/^\\([!"#$%&'()*+,\-./:;<=>?@\[\]\\^_`{|}~])/,_e=/^(`+)([^`]|[^`][\s\S]*?[^`])\1(?!`)/,j=/^( {2,}|\\)\n(?!\s*$)[ \t]*/,ve=/^(`+|[^`])(?:(?= {2,}\n)|[\s\S]*?(?:(?=[\\<!\[`*_]|\b_|$)|[^ ](?= {2,}\n)))/,M=/[\p{P}\p{S}]/u,N=/[\s\p{P}\p{S}]/u,P=/[^\s\p{P}\p{S}]/u,ye=b(/^((?![*_])punctSpace)/,`u`).replace(/punctSpace/g,N).getRegex(),be=/[\p{Pi}\p{Ps}"']/u,F=/(?!~)[\p{P}\p{S}]/u,xe=/(?!~)[\s\p{P}\p{S}]/u,Se=/(?:[^\s\p{P}\p{S}]|~)/u,Ce=b(/link|precode-code|html/,`g`).replace(`link`,/\[(?:[^\[\]`]|(?<a>`+)[^`]+\k<a>(?!`))*?\]\((?:\\[\s\S]|[^\\\(\)]|\((?:\\[\s\S]|[^\\\(\)])*\))*\)/).replace(`precode-`,ee?"(?<!`)()":"(^^|[^`])").replace(`code`,/(?<b>`+)[^`]+\k<b>(?!`)/).replace(`html`,/<(?! )[^<>]*?>/).getRegex(),I=/^(?:\*+(?:((?!\*)punct)|([^\s*]))?)|^_+(?:((?!_)punct)|([^\s_]))?/,we=b(I,`u`).replace(/punct/g,M).getRegex(),Te=b(I,`u`).replace(/punct/g,F).getRegex(),Ee=b(/^(?:\*+(?:((?!\*)(?!openQuote)punct)|([^\s*]))?)|^_+(?:((?!_)(?!openQuote)punct)|([^\s_]))?/,`u`).replace(/openQuote/g,be).replace(/punct/g,M).getRegex(),L=`^[^_*]*?__[^_*]*?\\*[^_*]*?(?=__)|[^*]+(?=[^*])|(?!\\*)punct(\\*+)(?=[\\s]|$)|notPunctSpace(\\*+)(?!\\*)(?=punctSpace|$)|(?!\\*)punctSpace(\\*+)(?=notPunctSpace)|[\\s](\\*+)(?!\\*)(?=punct)|(?!\\*)punct(\\*+)(?!\\*)(?=punct)|notPunctSpace(\\*+)(?=notPunctSpace)`,De=b(L,`gu`).replace(/notPunctSpace/g,P).replace(/punctSpace/g,N).replace(/punct/g,M).getRegex(),Oe=b(L,`gu`).replace(/notPunctSpace/g,Se).replace(/punctSpace/g,xe).replace(/punct/g,F).getRegex(),ke=b(`^[^_*]*?__[^_*]*?\\*[^_*]*?(?=__)|[^*]+(?=[^*])|(?!\\*)punct(\\*+)(?=[\\s]|$)|notPunctSpace(\\*+)(?!\\*)(?=punctSpace|$)|(?!\\*)[\\s](\\*+)(?=notPunctSpace)|[\\s](\\*+)(?!\\*)(?=punct)|(?!\\*)punct(\\*+)(?!\\*)(?=punct)|(?:(?!\\*)punct|notPunctSpace)(\\*+)(?!\\*)(?=notPunctSpace)`,`gu`).replace(/notPunctSpace/g,P).replace(/punctSpace/g,N).replace(/punct/g,M).getRegex(),Ae=b(`^[^_*]*?\\*\\*[^_*]*?_[^_*]*?(?=\\*\\*)|[^_]+(?=[^_])|(?!_)punct(_+)(?=[\\s]|$)|notPunctSpace(_+)(?!_)(?=punctSpace|$)|(?!_)punctSpace(_+)(?=notPunctSpace)|[\\s](_+)(?!_)(?=punct)|(?!_)punct(_+)(?!_)(?=punct)`,`gu`).replace(/notPunctSpace/g,P).replace(/punctSpace/g,N).replace(/punct/g,M).getRegex(),je=b(`^[^_*]*?\\*\\*[^_*]*?_[^_*]*?(?=\\*\\*)|[^_]+(?=[^_])|(?!_)punct(_+)(?=[\\s]|$)|notPunctSpace(_+)(?!_)(?=punctSpace|$)|(?!_)[\\s](_+)(?=notPunctSpace)|[\\s](_+)(?!_)(?=punct)|(?!_)punct(_+)(?!_)(?=punct)|(?:(?!_)punct|notPunctSpace)(_+)(?!_)(?=notPunctSpace)`,`gu`).replace(/notPunctSpace/g,P).replace(/punctSpace/g,N).replace(/punct/g,M).getRegex(),Me=b(/^~~?(?:((?!~)punct)|[^\s~])/,`u`).replace(/punct/g,M).getRegex(),Ne=b(`^[^~]+(?=[^~])|(?!~)punct(~~?)(?=[\\s]|$)|notPunctSpace(~~?)(?!~)(?=punctSpace|$)|(?!~)punctSpace(~~?)(?=notPunctSpace)|[\\s](~~?)(?!~)(?=punct)|(?!~)punct(~~?)(?!~)(?=punct)|notPunctSpace(~~?)(?=notPunctSpace)`,`gu`).replace(/notPunctSpace/g,P).replace(/punctSpace/g,N).replace(/punct/g,M).getRegex(),Pe=b(/\\(punct)/,`gu`).replace(/punct/g,M).getRegex(),Fe=b(/^<(scheme:[^\s\x00-\x1f<>]*|email)>/).replace(`scheme`,/[a-zA-Z][a-zA-Z0-9+.-]{1,31}/).replace(`email`,/[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+(@)[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+(?![-_])/).getRegex(),Ie=b(D).replace(`(?:-->|$)`,`-->`).getRegex(),Le=b(`^comment|^</[a-zA-Z][a-zA-Z0-9-]*\\s*>|^<[a-zA-Z][a-zA-Z0-9-]*(?:attribute)*?\\s*/?>|^<\\?[\\s\\S]*?\\?>|^<![a-zA-Z]+\\s[\\s\\S]*?>|^<!\\[CDATA\\[[\\s\\S]*?\\]\\]>`).replace(`comment`,Ie).replace(`attribute`,/\s+[a-zA-Z:_][\w.:-]*(?:\s*=\s*"[^"]*"|\s*=\s*'[^']*'|\s*=\s*[^\s"'=<>`]+)?/).getRegex(),Re=/\[(?:\\[\s\S]|[^\[\]\\])*\]/,R=b(/(?:\[(?:brackets|\\[\s\S]|[^\[\]\\])*\]|\\[\s\S]|`+(?!`)[^`]*?`+(?!`)|``+(?=\])|[^\[\]\\`])*?/).replace(`brackets`,Re).getRegex(),ze=b(/^!?\[(label)\]\(\s*(href)(?:(?:[ \t]+(?:\n[ \t]*)?|\n[ \t]*)(title))?\s*\)/).replace(`label`,R).replace(`href`,/<(?:\\.|[^\n<>\\])+>|[^ \t\n\x00-\x1f]+|(?=\))/).replace(`title`,/"(?:\\"?|[^"\\])*"|'(?:\\'?|[^'\\])*'|\((?:\\\)?|[^)\\])*\)/).getRegex(),Be=b(/^!?\[(label)\]\[(ref)\]/).replace(`label`,R).replace(`ref`,T).getRegex(),Ve=b(/^!?\[(ref)\](?:\[\])?/).replace(`ref`,T).getRegex(),He=/(?!\s*\])(?:\\[\s\S]|[^\[\]\\]){1,999}/,Ue=b(/(?:[^\[\]\\`]*(?:\[(?:brackets|\\[\s\S]|[^\[\]\\])*\]|\\[\s\S]|`+(?!`)[^`]*?`+(?!`)|``+(?=\]))){0,999}?[^\[\]\\`]*?/).replace(`brackets`,Re).getRegex(),We=b(`reflink|nolink(?!\\()`,`g`).replace(`reflink`,b(/^!?\[(label)\]\[(ref)\]/).replace(`label`,Ue).replace(`ref`,He).getRegex()).replace(`nolink`,b(/^!?\[(ref)\](?:\[\])?/).replace(`ref`,He).getRegex()).getRegex(),Ge=/[hH][tT][tT][pP][sS]?|[fF][tT][pP]/,Ke=b(/(?:mailto:email|xmpp:email(?:\/[A-Za-z0-9@.]+)?)/).replace(/email/g,/[A-Za-z0-9._+-]+@[a-zA-Z0-9-_]+(?:\.[a-zA-Z0-9-_]*[a-zA-Z0-9])+(?![\w-])/).getRegex(),z={_backpedal:v,anyPunctuation:Pe,autolink:Fe,blockSkip:Ce,br:j,code:_e,del:v,delLDelim:v,delRDelim:v,emStrongLDelim:we,emStrongRDelimAst:De,emStrongRDelimUnd:Ae,escape:ge,link:ze,nolink:Ve,punctuation:ye,reflink:Be,reflinkSearch:We,tag:Le,text:ve,url:v},qe={...z,emStrongLDelim:Ee,emStrongRDelimAst:ke,emStrongRDelimUnd:je,link:b(/^!?\[(label)\]\((.*?)\)/).replace(`label`,R).getRegex(),reflink:b(/^!?\[(label)\]\s*\[([^\]]*)\]/).replace(`label`,R).getRegex()},B={...z,emStrongRDelimAst:Oe,emStrongLDelim:Te,delLDelim:Me,delRDelim:Ne,url:b(/^emailProtocol|^((?:protocol):\/\/|www\.)(?:[a-zA-Z0-9\-]+\.?)+[^\s<]*|^email/).replace(`emailProtocol`,Ke).replace(`protocol`,Ge).replace(`email`,/[A-Za-z0-9._+-]+(@)[a-zA-Z0-9-_]+(?:\.[a-zA-Z0-9-_]*[a-zA-Z0-9])+(?![\w-])/).getRegex(),_backpedal:/(?:[^?!.,:;*_'"~()&]+|\([^)]*\)|&(?![a-zA-Z0-9]+;$)|[?!.,:;*_'"~)]+(?!$))+/,del:/^(~~?)(?=[^\s~])((?:\\[\s\S]|[^\\])*?(?:\\[\s\S]|[^\s~\\]))\1(?=[^~]|$)/,text:b(/^(?:[^a-zA-Z0-9](?=emailProtocol)|(`+|~+|[^`~])(?:(?=[`~])|(?= {2,}\n)|(?=[a-zA-Z0-9.!#$%&'*+\/=?_`{\|}~-]+@)|[\s\S]*?(?:(?=[\\<!\[`*~_]|\b_|protocol:\/\/|www\.|$)|[^ ](?= {2,}\n)|[^a-zA-Z0-9](?=emailProtocol)|[^a-zA-Z0-9.!#$%&'*+\/=?_`{\|}~-](?=[a-zA-Z0-9.!#$%&'*+\/=?_`{\|}~-]+@))))/).replace(`protocol`,Ge).replace(/emailProtocol/g,/(?:mailto|xmpp):/).getRegex()},Je={...B,br:b(j).replace(`{2,}`,`*`).getRegex(),text:b(B.text).replace(`\\b_`,`\\b_| {2,}\\n`).replace(/\{2,\}/g,`*`).getRegex()},V={normal:k,gfm:me,pedantic:he},H={normal:z,gfm:B,breaks:Je,pedantic:qe},Ye={"&":`&amp;`,"<":`&lt;`,">":`&gt;`,'"':`&quot;`,"'":`&#39;`},Xe=e=>Ye[e];function U(e,t){if(t){if(x.escapeTest.test(e))return e.replace(x.escapeReplace,Xe)}else if(x.escapeTestNoEncode.test(e))return e.replace(x.escapeReplaceNoEncode,Xe);return e}function Ze(e){return e.replace(x.numericCharacterReference,(e,t,n)=>{let r=t===void 0?Number.parseInt(n,16):Number.parseInt(t,10);return r===0||r>1114111||r>=55296&&r<=57343?`�`:String.fromCodePoint(r)})}function Qe(e){try{e=encodeURI(e).replace(x.percentDecode,`%`)}catch{return null}return e}function $e(e,t){var n;let r=e.replace(x.findPipe,(e,t,n)=>{let r=!1,i=t;for(;--i>=0&&n[i]===`\\`;)r=!r;return r?`|`:` |`}).split(x.splitPipe),i=0;if(r[0].trim()||r.shift(),r.length>0&&!((n=r.at(-1))!=null&&n.trim())&&r.pop(),t){if(r.length>t)r.splice(t);else for(;r.length<t;)r.push(``)}for(;i<r.length;i++)r[i]=r[i].trim().replace(x.slashPipe,`|`);return r}function W(e,t,n){let r=e.length;if(r===0)return``;let i=0;for(;i<r;){let a=e.charAt(r-i-1);if(a===t&&!n)i++;else if(a!==t&&n)i++;else break}return e.slice(0,r-i)}function et(e){let t=e.split(`
`),n=t.length-1;for(;n>=0&&x.blankLine.test(t[n]);)n--;return t.length-n<=2?e:t.slice(0,n+1).join(`
`)}function G(e){return e.trim().toLowerCase().toUpperCase().toLowerCase()}function tt(e,t){if(e.indexOf(t[1])===-1)return-1;let n=0;for(let r=0;r<e.length;r++)if(e[r]===`\\`)r++;else if(e[r]===t[0])n++;else if(e[r]===t[1]&&(n--,n<0))return r;return n>0?-2:-1}function nt(e,t=0){let n=t,r=``;for(let t of e)if(t===`	`){let e=4-n%4;r+=` `.repeat(e),n+=e}else r+=t,n++;return r}function rt(e,t,n,r,i){let a=t.href,o=t.title||null,s=e[1].replace(i.other.outputLinkReplace,`$1`),c=e[0].charAt(0)===`!`;r.state.inLink=!0;let l=r.state.linkEmitted,u=r.state.inRawBlock;r.state.linkEmitted=!1;let d=r.inlineTokens(s),f=r.state.linkEmitted;if(r.state.linkEmitted=l,r.state.inLink=!1,!c){if(f){r.state.inRawBlock=u;return}r.state.linkEmitted=!0}return{type:c?`image`:`link`,raw:n,href:a,title:o,text:s,tokens:d}}function it(e,t,n){let r=e.match(n.other.indentCodeCompensation);if(r===null)return t;let i=r[1];return t.split(`
`).map(e=>{let t=e.match(n.other.beginningSpace);if(t===null)return e;let[r]=t;return e.slice(Math.min(r.length,i.length))}).join(`
`)}function at(e,t,n,r){if(!t.includes(`<`))return!1;for(let i=0;i<t.length;i++){if(t[i]===`\\`){i++;continue}if(t[i]==="`"){let e=r.inline.code.exec(t.slice(i));if(e){i+=e[0].length-1;continue}}if(t[i]!==`<`)continue;let a=e.slice(n+i),o=r.inline.tag.exec(a)||r.inline.autolink.exec(a);if(o){if(o[0].length>t.length-i)return!0;i+=o[0].length-1}}return!1}var K=class{constructor(e){p(this,`options`,void 0),p(this,`rules`,void 0),p(this,`lexer`,void 0),this.options=e||g}space(e){let t=this.rules.block.newline.exec(e);if(t&&t[0].length>0)return{type:`space`,raw:t[0]}}code(e){let t=this.rules.block.code.exec(e);if(t){let e=this.options.pedantic?t[0]:et(t[0]);return{type:`code`,raw:e,codeBlockStyle:`indented`,text:e.replace(this.rules.other.codeRemoveIndent,``)}}}fences(e){let t=this.rules.block.fences.exec(e);if(t){let e=t[0],n=it(e,t[3]||``,this.rules);return{type:`code`,raw:e,lang:t[2]?t[2].trim().replace(this.rules.inline.anyPunctuation,`$1`):t[2],text:n}}}heading(e){let t=this.rules.block.heading.exec(e);if(t){let e=t[2].trim();if(this.rules.other.endingHash.test(e)){let t=W(e,`#`);(this.options.pedantic||!t||this.rules.other.endingSpaceTabChar.test(t))&&(e=t.trim())}return{type:`heading`,raw:W(t[0],`
`),depth:t[1].length,text:e,tokens:this.lexer.inline(e)}}}hr(e){let t=this.rules.block.hr.exec(e);if(t)return{type:`hr`,raw:W(t[0],`
`)}}blockquote(e){let t=this.rules.block.blockquote.exec(e);if(t){let e=W(t[0],`
`).split(`
`),n=``,r=``,i=[];for(;e.length>0;){let t=!1,a=[],o=0;for(;o<e.length;o++)if(this.rules.other.blockquoteStart.test(e[o]))a.push(e[o]),t=!0;else if(!t)a.push(e[o]);else break;e=e.slice(o);let s=a.join(`
`),c=s.replace(this.rules.other.blockquoteSetextReplace,`
    $1`).replace(this.rules.other.blockquoteSetextReplace2,``);n=n?`${n}
${s}`:s,r=r?`${r}
${c}`:c;let l=this.lexer.state.top;if(this.lexer.state.top=!0,this.lexer.blockTokens(c,i,!0),this.lexer.state.top=l,e.length===0)break;let u=i.at(-1);if((u==null?void 0:u.type)===`code`)break;if((u==null?void 0:u.type)===`blockquote`){let t=u,a=e.join(`
`),o=t.raw+`
`+a.replace(this.rules.other.blockquoteSetextReplace2,``),s=this.blockquote(o);i[i.length-1]=s;let c=o.substring(s.raw.length).replace(/^\n/,``),l=c?c.split(`
`).length:0,d=l?e.slice(0,-l):e;d.length>0&&(n=`${n}
${d.join(`
`)}`),r=r.substring(0,r.length-t.text.length)+s.text;break}if((u==null?void 0:u.type)===`list`){let t=u,a=t.raw+`
`+e.join(`
`),o=this.list(a);i[i.length-1]=o,n=n.substring(0,n.length-u.raw.length)+o.raw,r=r.substring(0,r.length-t.raw.length)+o.raw,e=a.substring(i.at(-1).raw.length).split(`
`);continue}}return{type:`blockquote`,raw:n,tokens:i,text:r}}}list(e){let t=this.rules.block.list.exec(e);if(t){let n=t[1].trim(),r=n.length>1,i={type:`list`,raw:``,ordered:r,start:r?+n.slice(0,-1):``,loose:!1,items:[]};n=r?`\\d{1,9}\\${n.slice(-1)}`:`\\${n}`,this.options.pedantic&&(n=r?n:`[*+-]`);let a=this.rules.other.listItemRegex(n),o=!1;for(;e;){let n=!1,r=``,s=``;if(!(t=a.exec(e))||this.rules.block.hr.test(e))break;r=t[0],e=e.substring(r.length);let c=t[2].split(`
`,1)[0],l=t[1].length,u=this.options.pedantic?nt(c,l):c.replace(this.rules.other.leadingSpaceTab,e=>nt(e,l)),d=e.split(`
`,1)[0],f=!u.trim(),p=0;if(this.options.pedantic?(p=2,s=u.trimStart()):f?p=l+1:(p=u.search(this.rules.other.nonSpaceChar),p=p>4?1:p,s=u.slice(p),p+=l),f&&this.rules.other.blankLine.test(d)&&(r+=d+`
`,e=e.substring(d.length+1),n=!0),!n){let t=this.rules.other.nextBulletRegex(p),n=this.rules.other.hrRegex(p),i=this.rules.other.fencesBeginRegex(p),a=this.rules.other.headingBeginRegex(p),o=this.rules.other.htmlBeginRegex(p),c=this.rules.other.blockquoteBeginRegex(p);for(;e;){let l=e.split(`
`,1)[0],m;if(d=l,this.options.pedantic?(d=d.replace(this.rules.other.listReplaceNesting,`  `),m=d):m=d.replace(this.rules.other.leadingSpaceTab,e=>e.replace(this.rules.other.tabCharGlobal,`    `)),i.test(d)||a.test(d)||o.test(d)||c.test(d)||t.test(d)||n.test(d))break;if(m.search(this.rules.other.nonSpaceChar)>=p||!d.trim())s+=`
`+m.slice(p);else{if(f||u.replace(this.rules.other.tabCharGlobal,`    `).search(this.rules.other.nonSpaceChar)>=4||i.test(u)||a.test(u)||n.test(u))break;s+=`
`+d}f=!d.trim(),r+=l+`
`,e=e.substring(l.length+1),u=m.slice(p)}}i.loose||(o?i.loose=!0:this.rules.other.doubleBlankLine.test(r)&&(o=!0)),i.items.push({type:`list_item`,raw:r,task:!!this.options.gfm&&this.rules.other.listIsTask.test(s),loose:!1,text:s,tokens:[]}),i.raw+=r}let s=i.items.at(-1);if(s)s.raw=s.raw.trimEnd(),s.text=s.text.trimEnd();else return;i.raw=i.raw.trimEnd();for(let e of i.items)if(this.lexer.state.top=!1,e.tokens=this.lexer.blockTokens(e.text,[]),!i.loose){let t=e.tokens.filter(e=>e.type===`space`);i.loose=t.length>0&&t.some(e=>this.rules.other.anyLine.test(e.raw))}for(let e of i.items){let t=e.tokens[0];if(e.task&&((t==null?void 0:t.type)===`text`||(t==null?void 0:t.type)===`paragraph`)){e.text=e.text.replace(this.rules.other.listReplaceTask,``),t.raw=t.raw.replace(this.rules.other.listReplaceTask,``),t.text=t.text.replace(this.rules.other.listReplaceTask,``);for(let e=this.lexer.inlineQueue.length-1;e>=0;e--)if(this.rules.other.listIsTask.test(this.lexer.inlineQueue[e].src)){this.lexer.inlineQueue[e].src=this.lexer.inlineQueue[e].src.replace(this.rules.other.listReplaceTask,``);break}let n=this.rules.other.listTaskCheckbox.exec(e.raw);if(n){let t={type:`checkbox`,raw:n[0]+` `,checked:n[0]!==`[ ]`};e.checked=t.checked,i.loose?e.tokens[0]&&[`paragraph`,`text`].includes(e.tokens[0].type)&&`tokens`in e.tokens[0]&&e.tokens[0].tokens?(e.tokens[0].raw=t.raw+e.tokens[0].raw,e.tokens[0].text=t.raw+e.tokens[0].text,e.tokens[0].tokens.unshift(t)):e.tokens.unshift({type:`paragraph`,raw:t.raw,text:t.raw,tokens:[t]}):e.tokens.unshift(t)}}else e.task&&(e.task=!1)}if(i.loose)for(let e of i.items){e.loose=!0;for(let t of e.tokens)t.type===`text`&&(t.type=`paragraph`)}return i}}html(e){let t=this.rules.block.html.exec(e);if(t){let e=et(t[0]);return{type:`html`,block:!0,raw:e,pre:t[1]===`pre`||t[1]===`script`||t[1]===`style`,text:e}}}def(e){let t=this.rules.block.def.exec(e);if(t){let e=G(t[1]).replace(this.rules.other.multipleSpaceGlobal,` `),n=t[2]?t[2].replace(this.rules.other.hrefBrackets,`$1`).replace(this.rules.inline.anyPunctuation,`$1`):``,r=t[3]?t[3].substring(1,t[3].length-1).replace(this.rules.inline.anyPunctuation,`$1`):t[3];return{type:`def`,tag:e,raw:W(t[0],`
`),href:n,title:r}}}table(e){var t;let n=this.rules.block.table.exec(e);if(!n||!this.rules.other.tableDelimiter.test(n[2]))return;let r=$e(n[1]),i=n[2].replace(this.rules.other.tableAlignChars,``).split(`|`),a=(t=n[3])!=null&&t.trim()?n[3].replace(this.rules.other.tableRowBlankLine,``).split(`
`):[],o={type:`table`,raw:W(n[0],`
`),header:[],align:[],rows:[]};if(r.length===i.length){for(let e of i)this.rules.other.tableAlignRight.test(e)?o.align.push(`right`):this.rules.other.tableAlignCenter.test(e)?o.align.push(`center`):this.rules.other.tableAlignLeft.test(e)?o.align.push(`left`):o.align.push(null);for(let e=0;e<r.length;e++)o.header.push({text:r[e],tokens:this.lexer.inline(r[e]),header:!0,align:o.align[e]});for(let e of a)o.rows.push($e(e,o.header.length).map((e,t)=>({text:e,tokens:this.lexer.inline(e),header:!1,align:o.align[t]})));return o}}lheading(e){let t=this.rules.block.lheading.exec(e);if(t){let e=t[1].trim();return{type:`heading`,raw:W(t[0],`
`),depth:t[2].charAt(0)===`=`?1:2,text:e,tokens:this.lexer.inline(e)}}}paragraph(e){let t=this.rules.block.paragraph.exec(e);if(t){let e=t[1].charAt(t[1].length-1)===`
`?t[1].slice(0,-1):t[1];return{type:`paragraph`,raw:t[0],text:e,tokens:this.lexer.inline(e)}}}text(e){let t=this.rules.block.text.exec(e);if(t)return{type:`text`,raw:t[0],text:t[0],tokens:this.lexer.inline(t[0])}}escape(e){let t=this.rules.inline.escape.exec(e);if(t)return{type:`escape`,raw:t[0],text:t[1]}}tag(e){let t=this.rules.inline.tag.exec(e);if(t)return!this.lexer.state.inLink&&this.rules.other.startATag.test(t[0])?this.lexer.state.inLink=!0:this.lexer.state.inLink&&this.rules.other.endATag.test(t[0])&&(this.lexer.state.inLink=!1),!this.lexer.state.inRawBlock&&this.rules.other.startPreScriptTag.test(t[0])?this.lexer.state.inRawBlock=!0:this.lexer.state.inRawBlock&&this.rules.other.endPreScriptTag.test(t[0])&&(this.lexer.state.inRawBlock=!1),{type:`html`,raw:t[0],inLink:this.lexer.state.inLink,inRawBlock:this.lexer.state.inRawBlock,block:!1,text:t[0]}}link(e){let t=this.rules.inline.link.exec(e);if(t){let n=t[0].charAt(0)===`!`?2:1;if(!this.options.pedantic&&at(e,t[1],n,this.rules))return;let r=t[2].trim();if(!this.options.pedantic&&this.rules.other.startAngleBracket.test(r)){if(!this.rules.other.endAngleBracket.test(r))return;let e=W(r.slice(0,-1),`\\`);if((r.length-e.length)%2==0)return}else{let e=tt(t[2],`()`);if(e===-2)return;if(e>-1){let n=(t[0].indexOf(`!`)===0?5:4)+t[1].length+e;t[2]=t[2].substring(0,e),t[0]=t[0].substring(0,n).trim(),t[3]=``}}let i=t[2],a=``;if(this.options.pedantic){let e=this.rules.other.pedanticHrefTitle.exec(i);e&&(i=e[1],a=e[3])}else a=t[3]?t[3].slice(1,-1):``;return i=i.trim(),this.rules.other.startAngleBracket.test(i)&&(i=this.options.pedantic&&!this.rules.other.endAngleBracket.test(r)?i.slice(1):i.slice(1,-1)),rt(t,{href:i&&i.replace(this.rules.inline.anyPunctuation,`$1`),title:a&&a.replace(this.rules.inline.anyPunctuation,`$1`)},t[0],this.lexer,this.rules)}}reflink(e,t){let n;if((n=this.rules.inline.reflink.exec(e))||(n=this.rules.inline.nolink.exec(e))){let r=n[0].charAt(0)===`!`?2:1;if(!this.options.pedantic&&at(e,n[1],r,this.rules))return;let i=t[G((n[2]||n[1]).replace(this.rules.other.multipleSpaceGlobal,` `))];if(!i){let e=n[0].charAt(0);return{type:`text`,raw:e,text:e}}return rt(n,i,n[0],this.lexer,this.rules)}}emStrong(e,t,n=``){let r=this.rules.inline.emStrongLDelim.exec(e);if(!(!r||!r[1]&&!r[2]&&!r[3]&&!r[4]||r[4]&&n.match(this.rules.other.unicodeAlphaNumeric))&&(!(r[1]||r[3])||!n||this.rules.inline.punctuation.exec(n))){let i=[...r[0]].length-1,a,o,s=i,c=0,l=r[0][0],u=n===l,d=l===`*`?this.rules.inline.emStrongRDelimAst:this.rules.inline.emStrongRDelimUnd;for(d.lastIndex=0,t=t.slice(-1*e.length+i);(r=d.exec(t))!==null;){if(a=r[1]||r[2]||r[3]||r[4]||r[5]||r[6],!a)continue;if(o=[...a].length,r[3]||r[4]){s+=o;continue}if(r[5]||r[6]){if(i%3&&!((i+o)%3)){c+=o;continue}if(u)break}if(s-=o,s>0)continue;o=Math.min(o,o+s+c);let t=[...r[0]][0].length,n=e.slice(0,i+r.index+t+o);if(Math.min(i,o)%2){let e=n.slice(1,-1);return{type:`em`,raw:n,text:e,tokens:this.lexer.inlineTokens(e)}}let l=n.slice(2,-2);return{type:`strong`,raw:n,text:l,tokens:this.lexer.inlineTokens(l)}}}}codespan(e){let t=this.rules.inline.code.exec(e);if(t){let e=t[2].replace(this.rules.other.newLineCharGlobal,` `),n=this.rules.other.nonSpaceChar.test(e),r=this.rules.other.startingSpaceChar.test(e)&&this.rules.other.endingSpaceChar.test(e);return n&&r&&(e=e.substring(1,e.length-1)),{type:`codespan`,raw:t[0],text:e}}}br(e){let t=this.rules.inline.br.exec(e);if(t)return{type:`br`,raw:t[0]}}del(e,t,n=``){let r=this.rules.inline.delLDelim.exec(e);if(r&&(!r[1]||!n||this.rules.inline.punctuation.exec(n))){let n=[...r[0]].length-1,i,a,o=n,s=this.rules.inline.delRDelim;for(s.lastIndex=0,t=t.slice(-1*e.length+n);(r=s.exec(t))!==null;){if(i=r[1]||r[2]||r[3]||r[4]||r[5]||r[6],!i||(a=[...i].length,a!==n))continue;if(r[3]||r[4]){o+=a;continue}if(o-=a,o>0)continue;a=Math.min(a,a+o);let t=[...r[0]][0].length,s=e.slice(0,n+r.index+t+a),c=s.slice(n,-n);return{type:`del`,raw:s,text:c,tokens:this.lexer.inlineTokens(c)}}}}autolink(e){let t=this.rules.inline.autolink.exec(e);if(t){let e,n;return t[2]===`@`?(e=t[1],n=`mailto:`+e):(e=t[1],n=e),{type:`link`,raw:t[0],text:e,href:n,autolink:!0,tokens:[{type:`text`,raw:e,text:e}]}}}url(e){let t;if(t=this.rules.inline.url.exec(e)){let e,i;if(t[2]===`@`)e=t[0],i=`mailto:`+e;else{var n,r;let a;do a=t[0],t[0]=(n=(r=this.rules.inline._backpedal.exec(t[0]))==null?void 0:r[0])==null?``:n;while(a!==t[0]);e=t[0],i=t[1]===`www.`?`http://`+t[0]:t[0]}return{type:`link`,raw:t[0],text:e,href:i,autolink:!0,tokens:[{type:`text`,raw:e,text:e}]}}}inlineText(e){let t=this.rules.inline.text.exec(e);if(t){let e=this.lexer.state.inRawBlock;return{type:`text`,raw:t[0],text:e?t[0]:Ze(t[0]),escaped:e}}}},q=class e{constructor(e){p(this,`tokens`,void 0),p(this,`options`,void 0),p(this,`state`,void 0),p(this,`inlineQueue`,void 0),p(this,`tokenizer`,void 0),this.tokens=[],this.tokens.links=Object.create(null),this.options=e||g,this.options.tokenizer=this.options.tokenizer||new K,this.tokenizer=this.options.tokenizer,this.tokenizer.options=this.options,this.tokenizer.lexer=this,this.inlineQueue=[],this.state={inLink:!1,inRawBlock:!1,linkEmitted:!1,top:!0};let t={other:x,block:V.normal,inline:H.normal};this.options.pedantic?(t.block=V.pedantic,t.inline=H.pedantic):this.options.gfm&&(t.block=V.gfm,t.inline=this.options.breaks?H.breaks:H.gfm),this.tokenizer.rules=t}static get rules(){return{block:V,inline:H}}static lex(t,n){return new e(n).lex(t)}static lexInline(t,n){return new e(n).inlineTokens(t)}lex(e){e=e.replace(x.carriageReturn,`
`),this.blockTokens(e,this.tokens);for(let e=0;e<this.inlineQueue.length;e++){let t=this.inlineQueue[e];this.inlineTokens(t.src,t.tokens)}return this.inlineQueue=[],this.tokens}blockTokens(e,t=[],n=!1){this.tokenizer.lexer=this,this.options.pedantic&&(e=e.replace(x.tabCharGlobal,`    `).replace(x.spaceLine,``));let r=1/0;for(;e;){var i,a;if(e.length<r)r=e.length;else{this.infiniteLoopError(e.charCodeAt(0));break}let o;if((i=this.options.extensions)!=null&&(i=i.block)!=null&&i.some(n=>(o=n.call({lexer:this},e,t))?(e=e.substring(o.raw.length),t.push(o),!0):!1))continue;if(o=this.tokenizer.space(e)){e=e.substring(o.raw.length);let n=t.at(-1);o.raw.length===1&&n!==void 0?n.raw+=`
`:t.push(o);continue}if(o=this.tokenizer.code(e)){e=e.substring(o.raw.length);let n=t.at(-1);(n==null?void 0:n.type)===`paragraph`||(n==null?void 0:n.type)===`text`?(n.raw+=(n.raw.endsWith(`
`)?``:`
`)+o.raw,n.text+=`
`+o.text,this.inlineQueue.at(-1).src=n.text):t.push(o);continue}if(o=this.tokenizer.fences(e)){e=e.substring(o.raw.length),t.push(o);continue}if(o=this.tokenizer.heading(e)){e=e.substring(o.raw.length),t.push(o);continue}if(o=this.tokenizer.hr(e)){e=e.substring(o.raw.length),t.push(o);continue}if(o=this.tokenizer.blockquote(e)){e=e.substring(o.raw.length),t.push(o);continue}if(o=this.tokenizer.list(e)){e=e.substring(o.raw.length),t.push(o);continue}if(o=this.tokenizer.html(e)){e=e.substring(o.raw.length),t.push(o);continue}if(o=this.tokenizer.def(e)){e=e.substring(o.raw.length);let n=t.at(-1);(n==null?void 0:n.type)===`paragraph`||(n==null?void 0:n.type)===`text`?(n.raw+=(n.raw.endsWith(`
`)?``:`
`)+o.raw,n.text+=`
`+o.raw,this.inlineQueue.at(-1).src=n.text):this.tokens.links[o.tag]||(this.tokens.links[o.tag]={href:o.href,title:o.title},t.push(o));continue}if(o=this.tokenizer.table(e)){e=e.substring(o.raw.length),t.push(o);continue}if(o=this.tokenizer.lheading(e)){e=e.substring(o.raw.length),t.push(o);continue}let s=e;if((a=this.options.extensions)!=null&&a.startBlock){let t=1/0,n=e.slice(1),r;this.options.extensions.startBlock.forEach(e=>{r=e.call({lexer:this},n),typeof r==`number`&&r>=0&&(t=Math.min(t,r))}),t<1/0&&t>=0&&(s=e.substring(0,t+1))}if(this.state.top&&(o=this.tokenizer.paragraph(s))){let r=t.at(-1);n&&(r==null?void 0:r.type)===`paragraph`?(r.raw+=(r.raw.endsWith(`
`)?``:`
`)+o.raw,r.text+=`
`+o.text,this.inlineQueue.pop(),this.inlineQueue.at(-1).src=r.text):t.push(o),n=s.length!==e.length,e=e.substring(o.raw.length);continue}if(o=this.tokenizer.text(e)){e=e.substring(o.raw.length);let n=t.at(-1);(n==null?void 0:n.type)===`text`?(n.raw+=(n.raw.endsWith(`
`)?``:`
`)+o.raw,n.text+=`
`+o.text,this.inlineQueue.pop(),this.inlineQueue.at(-1).src=n.text):t.push(o);continue}if(e){this.infiniteLoopError(e.charCodeAt(0));break}}return this.state.top=!0,t}inline(e,t=[]){return this.inlineQueue.push({src:e,tokens:t}),t}linkInText(e){if(!e.includes(`[`))return!1;let t=this.tokenizer.rules.inline.link;for(let n of e.matchAll(this.tokenizer.rules.inline.blockSkip))if(t.test(n[0])&&e.charAt(n.index-1)!==`!`)return!0;for(let t of e.matchAll(this.tokenizer.rules.inline.reflinkSearch)){let e=t[0],n=e.lastIndexOf(`[`);if(e.charAt(0)!==`!`&&Object.hasOwn(this.tokens.links,G(e.slice(n+1,-1)))&&!(n>1&&this.linkInText(e.slice(1,n-1))))return!0}return!1}inlineTokens(e,t=[]){var n,r;this.tokenizer.lexer=this;let i=e;if(this.tokens.links&&e.includes(`[`)){let e=this.tokenizer.rules.inline.reflinkSearch,t=n=>{let r=n.lastIndexOf(`[`);if(!Object.hasOwn(this.tokens.links,G(n.slice(r+1,-1))))return n;if(r>1&&n.charAt(0)!==`!`){let i=n.slice(1,r-1);if(this.linkInText(i))return`[`+i.replace(e,t)+`][`+`a`.repeat(n.length-r-2)+`]`}return`[`+`a`.repeat(n.length-2)+`]`};i=i.replace(e,t)}i=i.replace(this.tokenizer.rules.inline.anyPunctuation,e=>`+`.repeat(e.length)),i=i.replace(this.tokenizer.rules.inline.blockSkip,(e,t,n)=>{let r=n?n.length:0;return e.slice(0,r)+`[`+`a`.repeat(e.length-r-2)+`]`}),i=(n=(r=this.options.hooks)==null||(r=r.emStrongMask)==null?void 0:r.call({lexer:this},i))==null?i:n;let a=!1,o=``,s=1/0;for(;e;){var c,l;if(e.length<s)s=e.length;else{this.infiniteLoopError(e.charCodeAt(0));break}a||(o=``),a=!1;let n;if((c=this.options.extensions)!=null&&(c=c.inline)!=null&&c.some(r=>(n=r.call({lexer:this},e,t))?(e=e.substring(n.raw.length),t.push(n),!0):!1))continue;if(n=this.tokenizer.escape(e)){e=e.substring(n.raw.length),t.push(n);continue}if(n=this.tokenizer.tag(e)){e=e.substring(n.raw.length),t.push(n);continue}if(n=this.tokenizer.link(e)){e=e.substring(n.raw.length),t.push(n);continue}if(n=this.tokenizer.reflink(e,this.tokens.links)){e=e.substring(n.raw.length);let r=t.at(-1);n.type===`text`&&(r==null?void 0:r.type)===`text`?(r.raw+=n.raw,r.text+=n.text):t.push(n);continue}if(n=this.tokenizer.emStrong(e,i,o)){e=e.substring(n.raw.length),t.push(n);continue}if(n=this.tokenizer.codespan(e)){e=e.substring(n.raw.length),t.push(n);continue}if(n=this.tokenizer.br(e)){e=e.substring(n.raw.length),t.push(n);continue}if(n=this.tokenizer.del(e,i,o)){e=e.substring(n.raw.length),t.push(n);continue}if(n=this.tokenizer.autolink(e)){e=e.substring(n.raw.length),t.push(n);continue}if(!this.state.inLink&&(n=this.tokenizer.url(e))){e=e.substring(n.raw.length),t.push(n);continue}let r=e;if((l=this.options.extensions)!=null&&l.startInline){let t=1/0,n=e.slice(1),i;this.options.extensions.startInline.forEach(e=>{i=e.call({lexer:this},n),typeof i==`number`&&i>=0&&(t=Math.min(t,i))}),t<1/0&&t>=0&&(r=e.substring(0,t+1))}if(n=this.tokenizer.inlineText(r)){e=e.substring(n.raw.length),n.raw.slice(-1)!==`_`&&(o=n.raw.slice(-1)),a=!0;let r=t.at(-1);(r==null?void 0:r.type)===`text`?(r.raw+=n.raw,r.text+=n.text):t.push(n);continue}if(e){this.infiniteLoopError(e.charCodeAt(0));break}}return t}infiniteLoopError(e){let t=`Infinite loop on byte: `+e;if(this.options.silent)console.error(t);else throw Error(t)}},J=class{constructor(e){p(this,`options`,void 0),p(this,`parser`,void 0),this.options=e||g}space(e){return``}code({text:e,lang:t,escaped:n}){var r;let i=(r=(t||``).match(x.notSpaceStart))==null?void 0:r[0],a=e?e.replace(x.endingNewline,``)+`
`:``;return i?`<pre><code class="language-`+U(i)+`">`+(n?a:U(a,!0))+`</code></pre>
`:`<pre><code>`+(n?a:U(a,!0))+`</code></pre>
`}blockquote({tokens:e}){return`<blockquote>
${this.parser.parse(e)}</blockquote>
`}html({text:e}){return e}def(e){return``}heading({tokens:e,depth:t}){return`<h${t}>${this.parser.parseInline(e)}</h${t}>
`}hr(e){return`<hr>
`}list(e){let t=e.ordered,n=e.start,r=``;for(let t=0;t<e.items.length;t++){let n=e.items[t];r+=this.listitem(n)}let i=t?`ol`:`ul`,a=t&&n!==1?` start="`+n+`"`:``;return`<`+i+a+`>
`+r+`</`+i+`>
`}listitem(e){return`<li>${this.parser.parse(e.tokens)}</li>
`}checkbox({checked:e}){return`<input `+(e?`checked="" `:``)+`disabled="" type="checkbox"> `}paragraph({tokens:e}){return`<p>${this.parser.parseInline(e)}</p>
`}table(e){let t=``,n=``;for(let t=0;t<e.header.length;t++)n+=this.tablecell(e.header[t]);t+=this.tablerow({text:n});let r=``;for(let t=0;t<e.rows.length;t++){let i=e.rows[t];n=``;for(let e=0;e<i.length;e++)n+=this.tablecell(i[e]);r+=this.tablerow({text:n})}return r&&(r=`<tbody>${r}</tbody>`),`<table>
<thead>
`+t+`</thead>
`+r+`</table>
`}tablerow({text:e}){return`<tr>
${e}</tr>
`}tablecell(e){let t=this.parser.parseInline(e.tokens),n=e.header?`th`:`td`;return(e.align?`<${n} align="${e.align}">`:`<${n}>`)+t+`</${n}>
`}strong({tokens:e}){return`<strong>${this.parser.parseInline(e)}</strong>`}em({tokens:e}){return`<em>${this.parser.parseInline(e)}</em>`}codespan({text:e}){return`<code>${U(e,!0)}</code>`}br(e){return`<br>`}del({tokens:e}){return`<del>${this.parser.parseInline(e)}</del>`}link({href:e,title:t,text:n,tokens:r,autolink:i}){let a=i?U(n,!0):this.parser.parseInline(r),o=Qe(e);if(o===null)return a;e=U(o,i);let s=`<a href="`+e+`"`;return t&&(s+=` title="`+U(t)+`"`),s+=`>`+a+`</a>`,s}image({href:e,title:t,text:n,tokens:r}){r&&(n=this.parser.parseInline(r,this.parser.textRenderer));let i=Qe(e);if(i===null)return U(n);e=i;let a=`<img src="${U(e)}" alt="${U(n)}"`;return t&&(a+=` title="${U(t)}"`),a+=`>`,a}text(e){return`tokens`in e&&e.tokens?this.parser.parseInline(e.tokens):`escaped`in e&&e.escaped?e.text:U(e.text)}},Y=class{strong({text:e}){return e}em({text:e}){return e}codespan({text:e}){return e}del({text:e}){return e}html({text:e}){return e}text({text:e}){return e}link({text:e}){return``+e}image({text:e}){return``+e}br(){return``}checkbox({raw:e}){return e}},X=class e{constructor(e){p(this,`options`,void 0),p(this,`renderer`,void 0),p(this,`textRenderer`,void 0),this.options=e||g,this.options.renderer=this.options.renderer||new J,this.renderer=this.options.renderer,this.renderer.options=this.options,this.renderer.parser=this,this.textRenderer=new Y}static parse(t,n){return new e(n).parse(t)}static parseInline(t,n){return new e(n).parseInline(t)}parse(e){this.renderer.parser=this;let t=``;for(let r=0;r<e.length;r++){var n;let i=e[r];if((n=this.options.extensions)!=null&&(n=n.renderers)!=null&&n[i.type]){let e=i,n=this.options.extensions.renderers[e.type].call({parser:this},e);if(n!==!1||![`space`,`hr`,`heading`,`code`,`table`,`blockquote`,`list`,`checkbox`,`html`,`def`,`paragraph`,`text`].includes(e.type)){t+=n||``;continue}}let a=i;switch(a.type){case`space`:t+=this.renderer.space(a);break;case`hr`:t+=this.renderer.hr(a);break;case`heading`:t+=this.renderer.heading(a);break;case`code`:t+=this.renderer.code(a);break;case`table`:t+=this.renderer.table(a);break;case`blockquote`:t+=this.renderer.blockquote(a);break;case`list`:t+=this.renderer.list(a);break;case`checkbox`:t+=this.renderer.checkbox(a);break;case`html`:t+=this.renderer.html(a);break;case`def`:t+=this.renderer.def(a);break;case`paragraph`:t+=this.renderer.paragraph(a);break;case`text`:t+=this.renderer.text(a);break;default:{let e=`Token with "`+a.type+`" type was not found.`;if(this.options.silent)return console.error(e),``;throw Error(e)}}}return t}parseInline(e,t=this.renderer){this.renderer.parser=this;let n=``;for(let i=0;i<e.length;i++){var r;let a=e[i];if((r=this.options.extensions)!=null&&(r=r.renderers)!=null&&r[a.type]){let e=this.options.extensions.renderers[a.type].call({parser:this},a);if(e!==!1||![`escape`,`html`,`link`,`image`,`checkbox`,`strong`,`em`,`codespan`,`br`,`del`,`text`].includes(a.type)){n+=e||``;continue}}let o=a;switch(o.type){case`escape`:n+=t.text(o);break;case`html`:n+=t.html(o);break;case`link`:n+=t.link(o);break;case`image`:n+=t.image(o);break;case`checkbox`:n+=t.checkbox(o);break;case`strong`:n+=t.strong(o);break;case`em`:n+=t.em(o);break;case`codespan`:n+=t.codespan(o);break;case`br`:n+=t.br(o);break;case`del`:n+=t.del(o);break;case`text`:n+=t.text(o);break;default:{let e=`Token with "`+o.type+`" type was not found.`;if(this.options.silent)return console.error(e),``;throw Error(e)}}}return n}},Z=(m=class{constructor(e){p(this,`options`,void 0),p(this,`block`,void 0),this.options=e||g}preprocess(e){return e}postprocess(e){return e}processAllTokens(e){return e}emStrongMask(e){return e}provideLexer(e=this.block){return e?q.lex:q.lexInline}provideParser(e=this.block){return e?X.parse:X.parseInline}},p(m,`passThroughHooks`,new Set([`preprocess`,`postprocess`,`processAllTokens`,`emStrongMask`])),p(m,`passThroughHooksRespectAsync`,new Set([`preprocess`,`postprocess`,`processAllTokens`])),m),Q=new class{constructor(...e){p(this,`defaults`,h()),p(this,`options`,this.setOptions),p(this,`parse`,this.parseMarkdown(!0)),p(this,`parseInline`,this.parseMarkdown(!1)),p(this,`Parser`,X),p(this,`Renderer`,J),p(this,`TextRenderer`,Y),p(this,`Lexer`,q),p(this,`Tokenizer`,K),p(this,`Hooks`,Z),this.use(...e)}walkTokens(e,t){let n=[];for(let i of e)switch(n=n.concat(t.call(this,i)),i.type){case`table`:{let e=i;for(let r of e.header)n=n.concat(this.walkTokens(r.tokens,t));for(let r of e.rows)for(let e of r)n=n.concat(this.walkTokens(e.tokens,t));break}case`list`:{let e=i;n=n.concat(this.walkTokens(e.items,t));break}default:{var r;let e=i;(r=this.defaults.extensions)!=null&&(r=r.childTokens)!=null&&r[e.type]?this.defaults.extensions.childTokens[e.type].forEach(r=>{let i=e[r].flat(1/0);n=n.concat(this.walkTokens(i,t))}):e.tokens&&(n=n.concat(this.walkTokens(e.tokens,t)))}}return n}use(...e){let t=this.defaults.extensions||{renderers:{},childTokens:{}};return e.forEach(e=>{let n={...e};if(n.async=this.defaults.async||n.async||!1,e.extensions&&(e.extensions.forEach(e=>{if(!e.name)throw Error(`extension name required`);if(`renderer`in e){let n=t.renderers[e.name];n?t.renderers[e.name]=function(...t){let r=e.renderer.apply(this,t);return r===!1&&(r=n.apply(this,t)),r}:t.renderers[e.name]=e.renderer}if(`tokenizer`in e){if(!e.level||e.level!==`block`&&e.level!==`inline`)throw Error(`extension level must be 'block' or 'inline'`);let n=t[e.level];n?n.unshift(e.tokenizer):t[e.level]=[e.tokenizer],e.start&&(e.level===`block`?t.startBlock?t.startBlock.push(e.start):t.startBlock=[e.start]:e.level===`inline`&&(t.startInline?t.startInline.push(e.start):t.startInline=[e.start]))}`childTokens`in e&&e.childTokens&&(t.childTokens[e.name]=e.childTokens)}),n.extensions=t),e.renderer){let t=this.defaults.renderer||new J(this.defaults);for(let n in e.renderer){if(!(n in t))throw Error(`renderer '${n}' does not exist`);if([`options`,`parser`].includes(n))continue;let r=n,i=e.renderer[r],a=t[r];t[r]=(...e)=>{let n=i.apply(t,e);return n===!1&&(n=a.apply(t,e)),n||``}}n.renderer=t}if(e.tokenizer){let t=this.defaults.tokenizer||new K(this.defaults);for(let n in e.tokenizer){if(!(n in t))throw Error(`tokenizer '${n}' does not exist`);if([`options`,`rules`,`lexer`].includes(n))continue;let r=n,i=e.tokenizer[r],a=t[r];t[r]=(...e)=>{let n=i.apply(t,e);return n===!1&&(n=a.apply(t,e)),n}}n.tokenizer=t}if(e.hooks){let t=this.defaults.hooks||new Z;for(let n in e.hooks){if(!(n in t))throw Error(`hook '${n}' does not exist`);if([`options`,`block`].includes(n))continue;let r=n,i=e.hooks[r],a=t[r];t[r]=Z.passThroughHooks.has(n)?e=>{if(this.defaults.async&&Z.passThroughHooksRespectAsync.has(n))return(async()=>{let n=await i.call(t,e);return a.call(t,n)})();let r=i.call(t,e);return a.call(t,r)}:(...e)=>{if(this.defaults.async)return(async()=>{let n=await i.apply(t,e);return n===!1&&(n=await a.apply(t,e)),n})();let n=i.apply(t,e);return n===!1&&(n=a.apply(t,e)),n}}n.hooks=t}if(e.walkTokens){let t=this.defaults.walkTokens,r=e.walkTokens;n.walkTokens=function(e){let n=[];return n.push(r.call(this,e)),t&&(n=n.concat(t.call(this,e))),n}}this.defaults={...this.defaults,...n}}),this}setOptions(e){return this.defaults={...this.defaults,...e},this}lexer(e,t){return q.lex(e,t==null?this.defaults:t)}parser(e,t){return X.parse(e,t==null?this.defaults:t)}parseMarkdown(e){return(t,n)=>{let r={...n},i={...this.defaults,...r},a=this.onError(!!i.silent,!!i.async);if(this.defaults.async===!0&&r.async===!1)return a(Error(`marked(): The async option was set to true by an extension. Remove async: false from the parse options object to return a Promise.`));if(typeof t>`u`||t===null)return a(Error(`marked(): input parameter is undefined or null`));if(typeof t!=`string`)return a(Error(`marked(): input parameter is of type `+Object.prototype.toString.call(t)+`, string expected`));if(i.hooks&&(i.hooks.options=i,i.hooks.block=e),i.async)return(async()=>{let n=i.hooks?await i.hooks.preprocess(t):t,r=await(i.hooks?await i.hooks.provideLexer(e):e?q.lex:q.lexInline)(n,i),a=i.hooks?await i.hooks.processAllTokens(r):r;i.walkTokens&&await Promise.all(this.walkTokens(a,i.walkTokens));let o=await(i.hooks?await i.hooks.provideParser(e):e?X.parse:X.parseInline)(a,i);return i.hooks?await i.hooks.postprocess(o):o})().catch(a);try{i.hooks&&(t=i.hooks.preprocess(t));let n=(i.hooks?i.hooks.provideLexer(e):e?q.lex:q.lexInline)(t,i);i.hooks&&(n=i.hooks.processAllTokens(n)),i.walkTokens&&this.walkTokens(n,i.walkTokens);let r=(i.hooks?i.hooks.provideParser(e):e?X.parse:X.parseInline)(n,i);return i.hooks&&(r=i.hooks.postprocess(r)),r}catch(e){return a(e)}}}onError(e,t){return n=>{if(n.message+=`
Please report this to https://github.com/markedjs/marked.`,e){let e=`<p>An error occurred:</p><pre>`+U(n.message+``,!0)+`</pre>`;return t?Promise.resolve(e):e}if(t)return Promise.reject(n);throw n}}};function $(e,t){return Q.parse(e,t)}$.options=$.setOptions=function(e){return Q.setOptions(e),$.defaults=Q.defaults,_($.defaults),$},$.getDefaults=h,$.defaults=g;function ot(...e){return Q.use(...e),$.defaults=Q.defaults,_($.defaults),$}$.use=ot,$.walkTokens=function(e,t){return Q.walkTokens(e,t)},$.parseInline=Q.parseInline,$.Parser=X,$.parser=X.parse,$.Renderer=J,$.TextRenderer=Y,$.Lexer=q,$.lexer=q.lex,$.Tokenizer=K,$.Hooks=Z,$.parse=$,$.options,$.setOptions,$.walkTokens,$.parseInline,X.parse,q.lex;var st=`# Как пользоваться сайтом садоводства

Инструкция устроена просто: **найдите строчку «Хочу…», которая совпадает с вашим желанием, и делайте по шагам.**

Сначала найдите свой раздел:

- **[Я садовод](#я-садовод)** — плачу взносы, передаю показания счётчика.
- **[Я казначей](#я-казначей)** — начисляю взносы, принимаю деньги, делаю отчёты.
- **[Я председатель](#я-председатель)** — веду реестр членов и участков.
- **[Я администратор](#я-администратор)** — обслуживаю сервер.

---

## Первый вход — это нужно всем

### Хочу войти в первый раз

1. Откройте сайт: **snt-platforma.ru**
2. Введите **логин** и **временный пароль** — их выдал председатель на бумажке.
3. Нажмите **«Войти»**.
4. Сайт сразу попросит придумать свой пароль. Это обязательно, пропустить нельзя.
5. В поле **«Временный пароль»** впишите тот, что с бумажки.
6. В поля **«Новый пароль»** и **«Новый пароль ещё раз»** впишите свой новый — **одинаково в оба**.
7. Нажмите **«Сохранить»**.

Готово. Бумажку с временным паролем можно выбросить.

> **Пароль должен быть не короче 10 символов.** Не подойдут: только цифры (\`1234567890\`), простые слова (\`пароль\`, \`qwerty\`), ваша фамилия или логин. Придумайте фразу: \`КотНаЗаборе7\` — и длинно, и запоминается.

### Хочу сменить пароль потом

1. Нажмите **три полоски** слева вверху — откроется меню.
2. Выберите **«Смена пароля»**.
3. Впишите текущий пароль, потом новый два раза.
4. **«Сохранить»**.

### Забыл пароль

Сам сайт пароль не восстанавливает. Позвоните председателю или казначею — они выдадут новый временный.

---

## Я садовод

### Хочу узнать, сколько я должен

1. Войдите на сайт.
2. Вы сразу на странице **«Главная»** — это ваш личный кабинет.
3. Вверху две карточки:
   - **слева — долг за электричество**,
   - **справа — всё остальное** (членские и целевые взносы).
4. Ниже — список: за что именно и сколько.

Если вместо долга зелёная галочка «Задолженности нет» — вы ничего не должны.

> Если написано **«Учётная запись не связана с членом СНТ»** — это не ошибка с вашей стороны. Позвоните председателю, он поправит за минуту.

### Хочу понять, откуда взялась сумма за свет

1. На **«Главной»** найдите строку с электричеством.
2. Под ней мелким шрифтом написано, сколько кВт·ч и по какому тарифу.
3. Ещё ниже — последнее показание вашего счётчика и дата.

> Если там написано **«расчётное»** — значит вы не сдали показание за месяц, и сумму посчитали по вашему среднему расходу. Передайте настоящее показание, и в следующий раз всё пересчитается: лишнего с вас не возьмут, а если по среднему насчитали больше, разницу вернут на ваш лицевой счёт.

### Хочу передать показания счётчика

1. Откройте меню (**три полоски** слева вверху).
2. Выберите **«Показания счётчика»**.
3. В поле **«Дата снятия показаний»** поставьте дату, когда вы смотрели на счётчик.
4. Впишите число со счётчика — **всё число целиком**, а не сколько вы нагорели за месяц.
5. Если счётчик двухтарифный — заполните ещё **«Ночное показание»**.
6. Можно приложить **фото счётчика** — тогда к вам не будет вопросов.
7. Нажмите **«Отправить»**.

> **Главная ошибка:** написать «нагорело 150». Нужно писать то, что показывает счётчик, например \`14350\`. Разницу сайт посчитает сам.

> Сдавайте показания **до конца месяца**. Показание, записанное сентябрьской датой, относится к сентябрю.

### Хочу заплатить

1. На **«Главной»** посмотрите список начислений.
2. **Напротив каждого** есть поле с суммой. По умолчанию там стоит весь долг.
3. Если платите не всё — **сотрите и впишите свою сумму** в нужные строки. Внизу видно **«Итого»**.
   - Кнопка **«Весь долг»** — заполнить всё заново.
   - Кнопка **«Очистить»** — обнулить все поля.
4. Нажмите **«Оплатить по QR из банка»**.
5. Откроется окно с QR-кодом.
6. Возьмите **телефон**, откройте **приложение своего банка**, найдите там сканер QR и наведите камеру на экран.
7. В приложении банка подставятся реквизиты и сумма. Проверьте и подтвердите перевод.

> **Банк может взять свою комиссию за перевод.** Это тариф вашего банка, товарищество к нему отношения не имеет и этих денег не получает.

> Деньги идут не мгновенно — обычно до следующего рабочего дня. Долг на сайте погасится после того, как казначей загрузит банковскую выписку. Не пугайтесь, если назавтра долг ещё висит.

### Не получается отсканировать код

В том же окне, ниже QR, написаны **реквизиты для перевода вручную**: получатель, счёт, ИНН, банк, БИК. Перепишите их в приложение банка. **В назначении платежа обязательно укажите номер участка** — без него казначей не поймёт, от кого деньги.

### Хочу заплатить вперёд за сезон

Платите любую сумму, больше текущего долга. Лишнее не пропадёт: оно ляжет **авансом на лицевой счёт вашего участка**, и вы увидите это на «Главной» синей строкой. Как только появятся новые начисления, аванс зачтётся сам.

---

## Я казначей

### Хочу начислить всем членский взнос

1. Меню → **«Начисления»**.
2. Вверху выберите **период** (месяц, за который начисляем).
3. Нажмите **«Членский взнос»**.
4. Впишите **сумму на один участок**.
5. В «Описание» можно написать, например, \`Членский взнос за 2026 год\`.
6. Нажмите **«Начислить всем»**.

Сайт скажет, скольким участкам начислил.

> Если появится **оранжевое предупреждение со списком участков** — у этих участков **не указан собственник**, им взнос не начислен и в кабинете его никто не увидит. Передайте список председателю, пусть закрепит участки за людьми.

### Хочу начислить целевой взнос

1. Меню → **«Начисления»**, выберите период.
2. Нажмите **«Целевой взнос»**.
3. **«Вид начисления»** — выберите из списка. Если нужного нет: впишите название прямо в это поле (например, \`Ремонт дороги\`) и нажмите **Enter** — вид создастся сам.
4. Впишите **сумму на участок** и описание.
5. Выберите, кому начислять:
   - **«Всем участкам»** — всем без исключения;
   - **«Выбранным участкам»** — появится поле, где можно отметить нужные участки (искать по номеру или фамилии).
6. Нажмите **«Начислить»**.

> Целевой взнос начисляется и на участки без собственника — так бывает по решению общего собрания. Но сайт предупредит вас об этом: такое начисление никто не увидит в личном кабинете, пока участок не закрепят за человеком.

### Хочу рассчитать электроэнергию за месяц

**Сначала проверьте, что всё готово:**

1. Меню → **«Электроэнергия»**.
2. Вкладка **«Тарифы»** — тариф на нужный месяц должен быть. Нет — **«Добавить тариф»**, укажите цену за кВт·ч и дату «Действует с».
3. Вкладка **«Счётчики»** — должен быть **главный счётчик** (общий на въезде в садоводство) и счётчики участков.
4. Вкладка **«Показания»** — за месяц должны быть показания: и главного счётчика, и участков.

**Теперь считаем:**

5. Меню → **«Начисления»** — убедитесь, что расчётный период за нужный месяц создан.
6. Вернитесь в **«Электроэнергия»**, вкладка **«Показания»**.
7. Вверху выберите **месяц**.
8. Нажмите **«Рассчитать»**.

Сайт сам посчитает расход каждого участка, разложит потери в сети и создаст начисления.

> **Обязательно прочитайте, что сайт ответит.** Если появится оранжевое предупреждение со списком участков — эти люди не сдали показания, им начислили по среднему. Свяжитесь с ними.

> **Период обязательно должен быть месячным.** Если завести период «2026» без месяца, расчёт откажется работать и скажет об этом: электричество считается помесячно.

> **Как считаются потери.** Сколько зашло на главный счётчик, столько и распределяется между участками. Разница между главным счётчиком и суммой счётчиков — это потери в проводах, они делятся пропорционально расходу. Товарищество собирает ровно столько, сколько платит энергосбыту, не больше и не меньше.

### Хочу разнести деньги из банковской выписки

1. Скачайте выписку из интернет-банка в формате **«1С:Клиент-Банк»** (обычно файл \`kl_to_1c.txt\`).
2. Меню → **«Банковская выписка»**.
3. Нажмите **«Файл выписки»**, выберите скачанный файл.
4. Нажмите **«Загрузить»**, потом **«Разобрать»**.
5. Сайт покажет список поступлений и напротив каждого — какой участок он опознал.
6. **Проверьте глазами.** Строки, где участок не определился, можно указать вручную.
7. Когда всё верно — нажмите **«Провести N платежей»**.

> **Разбор и проведение специально разделены.** Пока вы не нажали «Провести», ничего не меняется. Сделано так потому, что зачисление по ошибке — это чужой долг, закрытый чужими деньгами, и обнаруживается такое через месяцы.

> Строки, где участок не опознан, **не проводятся**. Разберитесь с ними отдельно и проведите вручную.

> Загрузить одну и ту же выписку дважды не страшно — повторы сайт узнаёт и платежи не задваивает.

### Хочу внести платёж, который принял наличными

1. Меню → **«Начисления»**, вкладка **«Платежи»**.
2. Нажмите **«Внести платёж»**.
3. Выберите **начисление**, за которое человек заплатил.
4. Впишите **сумму** и **дату**.
5. В «Способ» выберите **«Наличные»**.
6. **«Сохранить»**.

### Хочу посмотреть, кто сколько должен

1. Меню → **«Начисления»**, вкладка **«Долги»**.
2. Выберите период вверху.
3. Увидите список: участок, фамилия, начислено, оплачено, долг.

Красным — кто должен, зелёной галочкой — кто расплатился.

### Хочу выгрузить ведомость должников в Excel

1. Меню → **«Отчёты»**.
2. Нажмите кнопку скачивания ведомости задолженностей.
3. Файл \`.xlsx\` скачается — открывайте в Excel.

Там же можно **отправить ведомость на почту**: впишите адрес и нажмите «Отправить».

> В файле персональные данные садоводов. Не выкладывайте его в общий чат и не отправляйте посторонним.

---

## Я председатель

Вам доступно всё, что казначею, плюс реестр.

### Хочу добавить нового члена садоводства

1. Меню → **«Члены СНТ»**.
2. Нажмите **«+»**.
3. Заполните **«Фамилия»**, **«Имя»**, при необходимости отчество и телефон.
4. Укажите **«Дата вступления»**.
5. **«Сохранить»**.

Человек появился в реестре. **Но участка у него пока нет** — это отдельный шаг.

### Хочу закрепить участок за человеком

1. Меню → **«Участки»**.
2. Найдите нужный участок (есть поиск по номеру) и нажмите **«Изменить»**.
3. В поле **«Собственники»** начните вводить фамилию — появится подсказка из реестра.
4. Выберите человека.
5. **«Сохранить»**.

> Пока участок ни за кем не закреплён, начисления по нему **не попадут ни в один личный кабинет**. Это самая частая причина жалобы «мне ничего не видно».

### Хочу вписать двух собственников на один участок

В том же поле **«Собственники»** выберите **несколько человек** подряд. Так и оформляется общая собственность — долг будет виден обоим.

### Хочу сменить собственника участка

1. **«Участки»** → нужный участок → **«Изменить»**.
2. В поле «Собственники» **уберите старого** (крестик рядом с фамилией) и **выберите нового**.
3. **«Сохранить»**.

История владения сохранится: видно, кто владел участком раньше и до какой даты.

### Хочу выдать одному человеку логин и пароль

1. Меню → **«Члены СНТ»**.
2. Найдите человека и нажмите на строку — откроется карточка.
3. Внизу карточки нажмите **«Выдать доступ»**.
4. Откроется окно: **логин** и **временный пароль**.
5. **Запишите или нажмите «Скопировать» прямо сейчас.**
6. Передайте человеку логин и пароль лично.

> **Пароль показывается ровно один раз.** В базе хранится только его зашифрованный отпечаток — повторно показать не может никто, включая вас. Потерялся — сбрасывайте новый.

> Кнопка есть **только у председателя**. Казначей ведёт деньги, а не людей.

### Хочу понять, кому доступ уже выдан

В списке **«Члены СНТ»** напротив каждого стоит значок:

| Значок | Что значит |
|---|---|
| **серый перечёркнутый** | доступа нет, логин не выдавали |
| **оранжевый ключ** | пароль выдан, но человек ещё ни разу не входил |
| **зелёный щит** | человек вошёл и сменил пароль, пользуется кабинетом |

Оранжевых через пару недель после раздачи стоит обзвонить: скорее всего, потеряли бумажку.

### Человек потерял пароль

1. **«Члены СНТ»** → карточка человека.
2. Нажмите **«Сбросить пароль»**, подтвердите.
3. Новый временный пароль показан один раз — передайте лично.

> Старый пароль перестаёт работать сразу.

### Хочу выдать логины сразу всем

Это делается на сервере, одной командой — попросите администратора. Команда выдаёт **каждому свой пароль**, требует сменить при первом входе и складывает всё в файл, который нужно распечатать, раздать и удалить. Тем, у кого учётка уже есть, она ничего не меняет.

> **Никогда не делайте один общий пароль на всех.** Пока человек не вошёл впервые, его кабинет открыт любому, кто этот пароль знает, а внутри — фамилия, телефон, участок и долги.

### Хочу разобраться, почему человек не видит своё начисление

Попросите администратора выполнить проверку участка (\`diagnose_plot\`). Она пройдёт всю цепочку и скажет, где обрыв. Обычно причин три:

1. участок ни за кем не закреплён;
2. у человека нет учётной записи;
3. в реестре **два одинаковых ФИО**, участок закреплён за одной записью, а учётка заведена на другую.

---

## Я администратор

### Хочу выкатить обновление

\`\`\`bash
cd /opt/snt-platform
git pull origin claude/gardening-community-site-662hr6
docker compose restart caddy backend
\`\`\`

Миграции контейнер прогоняет сам при старте. После выката обновите страницу в браузере.

> **\`./deploy.sh\` для обновления не годится.** Он тянет \`origin main\` и перезаписывает \`Caddyfile\` голым \`:80\`, снимая HTTPS.

> **Перезапускать нужно и \`caddy\`**, а не только \`backend\`: \`Caddyfile\` смонтирован в контейнер.

### Хочу завести учётки всем членам товарищества

Сначала на одном человеке, чтобы проверить, что всё работает:

\`\`\`bash
docker compose exec -T backend python manage.py create_member_accounts \\
    --org 'ТСН "Здоровье"' --plot 87 --out /app/creds-87.csv
docker compose cp backend:/app/creds-87.csv ./creds-87.csv
docker compose exec -T backend rm -f /app/creds-87.csv
\`\`\`

Открыли файл, вошли под этим логином, убедились, что кабинет работает — теперь всем:

\`\`\`bash
docker compose exec -T backend python manage.py create_member_accounts \\
    --org 'ТСН "Здоровье"' --out /app/member-credentials.csv
docker compose cp backend:/app/member-credentials.csv ./member-credentials.csv
docker compose exec -T backend rm -f /app/member-credentials.csv
\`\`\`

> **В файле пароли и персональные данные всех садоводов.** Права 600 ставятся автоматически. Раздайте и удалите: \`rm -f member-credentials.csv\`.

> Команда идемпотентна: у кого учётка уже есть, того пропускает. Повторный запуск безопасен.

> Не выводите файл в терминал через \`cat\` — пароли попадут в историю команд.

### Хочу понять, почему начисление не видно в кабинете

\`\`\`bash
docker compose exec -T backend python manage.py diagnose_plot 87
\`\`\`

Команда пройдёт цепочку **начисление → участок → владение → член → учётная запись** и покажет, на каком звене обрыв. ФИО маскируются, вывод можно показывать кому угодно. Полные имена — с ключом \`--full\`.

### Хочу проверить, что ничего не сломалось

Два набора проверок. Оба поднимают временную базу и ничего боевого не трогают.

\`\`\`bash
scripts/check_postgres.sh      # 114 проверок API на настоящем PostgreSQL
scripts/check_browser.sh       # проверка, что страницы действительно рисуются
\`\`\`

> **Почему не SQLite.** SQLite молча игнорирует \`select_for_update\`, и целый класс ошибок на нём не воспроизводится.

> **Почему нужен браузер.** Белый экран фронтенд отдаёт молча: API отвечает 200, все серверные проверки проходят, а человек смотрит в пустую страницу.

Проверку API можно запускать и на боевом — она строит себе отдельные данные и откатывает транзакцию:

\`\`\`bash
docker compose exec -T backend python manage.py check_user_paths
\`\`\`

### Хочу сделать резервную копию

\`\`\`bash
bash scripts/backup.sh
\`\`\`

Копия шифруется и уходит на Яндекс Диск. Настроено в cron на 03:00.

> Копия, которую ни разу не разворачивали, — это не копия. Проверяйте восстановление хотя бы раз в сезон.

---

## Если что-то пошло не так

| Что вижу | Что это значит |
|---|---|
| **Белый экран** | Старая версия страницы в браузере. Обновите с **Ctrl+Shift+R**. |
| **«Ошибка 500»** | Сломался сервер. Нужен администратор: \`docker compose logs --tail=100 backend\`. |
| **«Сервер не отвечает»** | Нет связи или сервер не запущен. |
| **«Неверный логин или пароль»** | Опечатка. Пароль чувствителен к заглавным буквам и раскладке. |
| **«Нужно сменить временный пароль»** | Вы ещё не меняли выданный пароль. Смените — остальное откроется. |
| **«Не выбрано СНТ»** | Только у администратора: выберите товарищество переключателем вверху. |
| **«Задолженности нет», хотя долг есть** | Ваша учётка не связана с членом СНТ — к председателю. |
| **В кабинете пусто, а начисление сделано** | Участок не закреплён за человеком — к председателю. |
`,ct={class:`help-page`},lt={class:`help-bar`},ut={class:`help-bar-inner`},dt=[`innerHTML`],ft=s({__name:`HelpPage`,setup(s){let u=c(),d=o(),f=i(()=>d.isAuthenticated?`На главную`:`Ко входу`);function p(){u.push(d.isAuthenticated?`/dashboard`:`/login`)}function m(){window.print()}function h(e){return String(e).toLowerCase().replace(/<[^>]+>/g,``).replace(/[^\p{L}\p{N}\s-]/gu,``).trim().replace(/\s+/g,`-`)}let g=new $.Renderer;g.heading=function({tokens:e,depth:t}){let n=this.parser.parseInline(e);return`<h${t} id="${h(this.parser.parseInline(e,this.parser.textRenderer))}">${n}</h${t}>\n`};let _=i(()=>$.parse(st,{renderer:g,gfm:!0,breaks:!1}));return(i,o)=>(n(),t(`div`,ct,[e(`div`,lt,[e(`div`,ut,[r(a,{flat:``,dense:``,icon:`arrow_back`,label:f.value,onClick:p},null,8,[`label`]),r(l),r(a,{flat:``,dense:``,icon:`print`,label:`Распечатать`,class:`gt-xs`,onClick:m})])]),e(`article`,{class:`help-body`,innerHTML:_.value},null,8,dt)]))}},[[`__scopeId`,`data-v-b213638f`]]);export{ft as default};