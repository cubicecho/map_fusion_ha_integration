/*! map-fusion-panel v0.4.0 built from frontend/src, do not edit */
var pt=Object.defineProperty,ft=Object.defineProperties;var mt=Object.getOwnPropertyDescriptors;var Z=Object.getOwnPropertySymbols;var gt=Object.prototype.hasOwnProperty,vt=Object.prototype.propertyIsEnumerable;var F=(r,i,t)=>i in r?pt(r,i,{enumerable:!0,configurable:!0,writable:!0,value:t}):r[i]=t,L=(r,i)=>{for(var t in i||(i={}))gt.call(i,t)&&F(r,t,i[t]);if(Z)for(var t of Z(i))vt.call(i,t)&&F(r,t,i[t]);return r},J=(r,i)=>ft(r,mt(i));var p=(r,i,t)=>F(r,typeof i!="symbol"?i+"":i,t);var O=(r,i,t)=>new Promise((e,n)=>{var s=d=>{try{l(t.next(d))}catch(o){n(o)}},a=d=>{try{l(t.throw(d))}catch(o){n(o)}},l=d=>d.done?e(d.value):Promise.resolve(d.value).then(s,a);l((t=t.apply(r,i)).next())});var tt=["nw","n","ne","e","se","s","sw","w"];function v(r,i){let t=i>0?Math.round(r/i)*i:r;return Math.round(t*1e3)/1e3}function z(r,i){return{x:v(r.x,i),y:v(r.y,i),width:v(r.width,i),height:v(r.height,i)}}function $(r,i,t,e,n){if(i==="move")return{x:v(r.x+t,n),y:v(r.y+e,n),width:r.width,height:r.height};let s=r.x,a=r.y,l=r.x+r.width,d=r.y+r.height,o=Math.max(.1,n);i.indexOf("w")!==-1&&(s=Math.min(v(s+t,n),l-o)),i.indexOf("e")!==-1&&(l=Math.max(v(l+t,n),s+o)),i.indexOf("n")!==-1&&(a=Math.min(v(a+e,n),d-o)),i.indexOf("s")!==-1&&(d=Math.max(v(d+e,n),a+o));let c=h=>Math.round(h*1e3)/1e3;return{x:c(s),y:c(a),width:c(l-s),height:c(d-a)}}function et(r,i){let t=i.indexOf("w")!==-1?r.x:i.indexOf("e")!==-1?r.x+r.width:r.x+r.width/2,e=i.indexOf("n")!==-1?r.y:i.indexOf("s")!==-1?r.y+r.height:r.y+r.height/2;return[t,e]}function rt(r,i=3,t=3){return r?{x:Math.round((r.x+r.width+.5)*10)/10,y:Math.round(r.y*10)/10,width:i,height:t}:{x:0,y:0,width:i,height:t}}function N(r){if(!r.length)return null;let i=1/0,t=1/0,e=-1/0,n=-1/0;for(let s of r)i=Math.min(i,s.x),t=Math.min(t,s.y),e=Math.max(e,s.x+s.width),n=Math.max(n,s.y+s.height);return{x:i,y:t,width:e-i,height:n-t}}function B(r,i){let t=Math.min(r.x+r.width,i.x+i.width)-Math.max(r.x,i.x),e=Math.min(r.y+r.height,i.y+i.height)-Math.max(r.y,i.y);return t>0&&e>0?t*e:0}function nt(r){let i=N(r)||{x:0,y:0,width:8,height:6},t=Math.floor(i.x-1),e=Math.floor(i.y-1),n=Math.ceil(i.x+i.width+1),s=Math.ceil(i.y+i.height+1);return{x:t,y:e,width:n-t,height:s-e}}function A(r,i,t){let e=!1;for(let n=0,s=t.length-1;n<t.length;s=n++){let[a,l]=t[n],[d,o]=t[s];l>i!=o>i&&r<(d-a)*(i-l)/(o-l)+a&&(e=!e)}return e}function I(r){let i=t=>t.toFixed(3);return r.filter(t=>t.length>=3).map(t=>"M"+t.map(e=>`${i(e[0])} ${i(e[1])}`).join(" L")+" Z").join(" ")}function j(r,i){if(r.length!==1||r[0].length!==4)return!1;let t=(e,n)=>Math.abs(e-n)<.002;return r[0].every(([e,n])=>(t(e,i.x)||t(e,i.x+i.width))&&(t(n,i.y)||t(n,i.y+i.height)))}function it(r,i,t,e){let n=Math.min(t.width/e.width,t.height/e.height)||1,s=(t.width-e.width*n)/2,a=(t.height-e.height*n)/2;return[e.x+(r-t.left-s)/n,e.y+(i-t.top-a)/n]}var E=3,x=r=>Math.round(r*1e3)/1e3+0;function V(r){return[[r.x,r.y],[x(r.x+r.width),r.y],[x(r.x+r.width),x(r.y+r.height)],[r.x,x(r.y+r.height)]]}function k(r){if(!r.length)return{x:0,y:0,width:0,height:0};let i=1/0,t=1/0,e=-1/0,n=-1/0;for(let[s,a]of r)i=Math.min(i,s),t=Math.min(t,a),e=Math.max(e,s),n=Math.max(n,a);return{x:i,y:t,width:x(e-i),height:x(n-t)}}function st(r){let i=0;for(let t=0,e=r.length-1;t<r.length;e=t++)i+=r[e][0]*r[t][1]-r[t][0]*r[e][1];return i/2}function P(r){return Math.abs(st(r))}function _(r){let i=st(r);if(Math.abs(i)<1e-9){let n=k(r);return[n.x+n.width/2,n.y+n.height/2]}let t=0,e=0;for(let n=0,s=r.length-1;n<r.length;s=n++){let[a,l]=r[s],[d,o]=r[n],c=a*o-d*l;t+=(a+d)*c,e+=(l+o)*c}return[t/(6*i),e/(6*i)]}function C(r){let i=null;for(let t of r)t.length>=3&&(!i||P(t)>P(i))&&(i=t);return i}function R(r){let i=[];for(let t of r){let e=[x(t[0]),x(t[1])],n=i[i.length-1];(!n||n[0]!==e[0]||n[1]!==e[1])&&i.push(e)}for(;i.length>1&&i[0][0]===i[i.length-1][0]&&i[0][1]===i[i.length-1][1];)i.pop();return i}function ot(r,i){let t=r[i],e=r[(i+1)%r.length],n=r.slice();return n.splice(i+1,0,[x((t[0]+e[0])/2),x((t[1]+e[1])/2)]),n}function at(r,i){if(r.length<=E||i<0||i>=r.length)return r.slice();let t=r.slice();return t.splice(i,1),t}function G(r,i,t){let e=r.slice();return e[i]=[x(t[0]),x(t[1])],e}function K(r,i,t,e){let n=k(r),s=v(n.x+i,e)-n.x,a=v(n.y+t,e)-n.y;return r.map(l=>[x(l[0]+s),x(l[1]+a)])}function xt(r,i,t){let e=[[i[0],r[1]],[t[0],r[1]],[r[0],i[1]],[r[0],t[1]]],n=e[0],s=1/0;for(let a of e){let l=Math.abs(a[0]-r[0])+Math.abs(a[1]-r[1]);l<s&&(n=a,s=l)}return n}function U(r,i,t,e,n,s=!1){let a=r[i],l=[v(a[0]+t,n),v(a[1]+e,n)];if(s&&r.length>=3){let d=r.length;l=xt(l,r[(i+d-1)%d],r[(i+1)%d])}return G(r,i,l)}function w(r,i,t){let e=(i[0]-r[0])*(t[1]-r[1])-(i[1]-r[1])*(t[0]-r[0]);return Math.abs(e)<1e-12?0:e>0?1:-1}function D(r,i,t){return Math.min(r[0],i[0])<=t[0]&&t[0]<=Math.max(r[0],i[0])&&Math.min(r[1],i[1])<=t[1]&&t[1]<=Math.max(r[1],i[1])}function bt(r,i,t,e){let n=w(r,i,t),s=w(r,i,e),a=w(t,e,r),l=w(t,e,i);return n!==s&&a!==l?!0:n===0&&D(r,i,t)||s===0&&D(r,i,e)||a===0&&D(t,e,r)||l===0&&D(t,e,i)}function yt(r,i,t){return w(i,r,t)!==0?!1:(r[0]-i[0])*(t[0]-i[0])+(r[1]-i[1])*(t[1]-i[1])>0}function wt(r){let i=r.length;if(i<3)return!1;for(let t=0;t<i;t++){let e=r[t],n=r[(t+1)%i];if(yt(e,n,r[(t+2)%i]))return!0;for(let s=t+2;s<i;s++)if(!(t===0&&s===i-1)&&bt(e,n,r[s],r[(s+1)%i]))return!0}return!1}function W(r){let i=R(r);return i.length<E?"The shape needs at least 3 different corners.":wt(i)?"The outline crosses itself. Move a corner so the edges don't cross.":P(i)<1e-4?"The shape has no area.":null}function lt(r,i,t){let e=t[0]-i[0],n=t[1]-i[1],s=e*e+n*n,a=s?((r[0]-i[0])*e+(r[1]-i[1])*n)/s:0;a=Math.max(0,Math.min(1,a));let l=r[0]-(i[0]+a*e),d=r[1]-(i[1]+a*n);return Math.sqrt(l*l+d*d)}function Q(r,i){let t=[];for(let n=0;n<r.length;n++)t.push(n===0||n===r.length-1);let e=[[0,r.length-1]];for(;e.length;){let[n,s]=e.pop(),a=-1,l=i;for(let d=n+1;d<s;d++){let o=lt(r[d],r[n],r[s]);o>l&&(l=o,a=d)}a!==-1&&(t[a]=!0,e.push([n,a],[a,s]))}return r.filter((n,s)=>t[s])}function kt(r,i){let t=r.length;if(t<=4||i<=0)return r.slice();let e=0,n=-1;for(let l=1;l<t;l++){let d=r[l][0]-r[0][0],o=r[l][1]-r[0][1];d*d+o*o>n&&(e=l,n=d*d+o*o)}let s=Q(r.slice(0,e+1),i),a=Q(r.slice(e).concat([r[0]]),i);return s.slice(0,-1).concat(a.slice(0,-1))}function dt(r,i){let t=C(r);if(t)for(let e of[.1,.05,.02]){let n=R(kt(t,e).map(s=>[v(s[0],.01),v(s[1],.01)]));if(!W(n))return n}return V(z(i,.01))}function Pt(r,i){let t=1/0;for(let e=0,n=i.length-1;e<i.length;n=e++)t=Math.min(t,lt(r,i[n],i[e]));return t}function S(r,i){return A(r[0],r[1],i)&&Pt(r,i)>.001}function ct(r,i){if(r.length<3||i.length<3||B(k(r),k(i))<=0)return!1;for(let n=0,s=r.length-1;n<r.length;s=n++)for(let a=0,l=i.length-1;a<i.length;l=a++){let d=r[s],o=r[n],c=i[l],h=i[a];if(w(d,o,c)*w(d,o,h)<0&&w(c,h,d)*w(c,h,o)<0)return!0}if(r.some(n=>S(n,i))||i.some(n=>S(n,r)))return!0;let t=_(r),e=_(i);return S(t,r)&&S(t,i)||S(e,i)&&S(e,r)}var ht=`
:host {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--primary-background-color);
  color: var(--primary-text-color);
  font-family: var(--ha-font-family-body, var(--paper-font-body1_-_font-family, sans-serif));
}
.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  height: var(--header-height, 56px);
  padding: 0 12px;
  background: var(--app-header-background-color, var(--primary-color));
  color: var(--app-header-text-color, var(--text-primary-color, #fff));
  border-bottom: var(--app-header-border-bottom, none);
  box-sizing: border-box;
  flex: none;
}
.title { flex: 1; font-size: 20px; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.toolbar select {
  font: inherit;
  font-size: 14px;
  padding: 4px 8px;
  border-radius: 6px;
  border: 1px solid rgba(255,255,255,0.5);
  background: rgba(255,255,255,0.15);
  color: inherit;
}
.toolbar option { color: var(--primary-text-color); background: var(--card-background-color); }
.body { display: flex; flex: 1; min-height: 0; }
:host([narrow]) .body { flex-direction: column; overflow: auto; }
.map-wrap { flex: 1; min-width: 0; min-height: 300px; padding: 12px; box-sizing: border-box; display: flex; }
.map {
  flex: 1;
  width: 100%;
  height: 100%;
  background: var(--card-background-color, #fff);
  border-radius: 12px;
  touch-action: none;
  user-select: none;
  outline: none;
}
.map:focus-visible { box-shadow: 0 0 0 2px var(--primary-color); }
.grid line { stroke: var(--divider-color, #e0e0e0); stroke-width: 1; vector-effect: non-scaling-stroke; }
.grid line.axis { stroke: var(--secondary-text-color, #9e9e9e); }
.tick { fill: var(--secondary-text-color, #757575); font-family: sans-serif; }
.room {
  fill: var(--secondary-background-color, #eceff1);
  stroke: var(--secondary-text-color, #9e9e9e);
  stroke-width: 1;
  vector-effect: non-scaling-stroke;
  cursor: pointer;
}
.room.manual { stroke-dasharray: 5 3; }
.room:hover { fill: color-mix(in srgb, var(--primary-color) 15%, var(--secondary-background-color, #eceff1)); }
.room.selected { stroke: var(--primary-color); stroke-width: 2; }
.room.ghost { fill-opacity: 0.35; stroke-dasharray: 5 3; }
.unlinked { fill: none; stroke: var(--disabled-text-color, #bdbdbd); stroke-dasharray: 4 3; vector-effect: non-scaling-stroke; }
.label {
  fill: var(--primary-text-color);
  text-anchor: middle;
  dominant-baseline: middle;
  pointer-events: none;
  font-family: sans-serif;
  paint-order: stroke;
  stroke: var(--card-background-color, #fff);
  stroke-linejoin: round;
}
.draft {
  fill: #ff9800;
  fill-opacity: 0.4;
  stroke: #e65100;
  stroke-width: 2;
  vector-effect: non-scaling-stroke;
  cursor: move;
}
path.draft { stroke-linejoin: round; }
.draft.invalid { fill: #f44336; stroke: #b71c1c; }
.vertex { fill: #fff; stroke: #e65100; stroke-width: 2; vector-effect: non-scaling-stroke; cursor: grab; }
.vertex.selected { fill: #e65100; stroke: #fff; }
.midpoint { fill: #e65100; fill-opacity: 0.55; stroke: #fff; stroke-width: 1; vector-effect: non-scaling-stroke; cursor: copy; }
.midpoint:hover { fill-opacity: 1; }
.handle { fill: #fff; stroke: #e65100; stroke-width: 2; vector-effect: non-scaling-stroke; }
.handle-n, .handle-s { cursor: ns-resize; }
.handle-e, .handle-w { cursor: ew-resize; }
.handle-ne, .handle-sw { cursor: nesw-resize; }
.handle-nw, .handle-se { cursor: nwse-resize; }
.draft-label {
  fill: #bf360c;
  font-weight: bold;
  text-anchor: middle;
  dominant-baseline: middle;
  pointer-events: none;
  font-family: sans-serif;
  paint-order: stroke;
  stroke: #fff;
  stroke-linejoin: round;
}
.side {
  width: 320px;
  flex: none;
  overflow-y: auto;
  padding: 12px 16px 24px 4px;
  box-sizing: border-box;
}
:host([narrow]) .side { width: auto; padding: 0 12px 24px; }
.editor {
  background: var(--card-background-color, #fff);
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 8px;
}
h2 { margin: 0 0 4px; font-size: 18px; font-weight: 500; }
h3 { margin: 16px 0 6px; font-size: 13px; font-weight: 500; color: var(--secondary-text-color); text-transform: uppercase; letter-spacing: 0.04em; }
.hint { color: var(--secondary-text-color); font-size: 14px; line-height: 1.4; }
.hint.small { font-size: 12px; margin-top: 8px; }
.warning { color: var(--warning-color, #e65100); font-size: 13px; margin-top: 8px; }
.warning[hidden] { display: none; }
.error { color: var(--error-color, #db4437); padding: 16px 0; }
.status { margin-top: 8px; font-size: 13px; color: var(--secondary-text-color); }
.fields { display: grid; grid-template-columns: 1fr 1fr; gap: 10px 12px; margin-top: 12px; }
.fields label { min-width: 0; display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--secondary-text-color); }
.fields input, .fields select {
  font: inherit;
  font-size: 15px;
  padding: 6px 8px;
  border: 1px solid var(--divider-color, #ccc);
  border-radius: 6px;
  background: var(--primary-background-color);
  color: var(--primary-text-color);
  min-width: 0;
  width: 100%;
  box-sizing: border-box;
}
.segmented { display: inline-flex; margin-top: 12px; border: 1px solid var(--primary-color); border-radius: 16px; overflow: hidden; }
.seg {
  font: inherit;
  font-size: 13px;
  padding: 5px 14px;
  border: none;
  background: transparent;
  color: var(--primary-color);
  cursor: pointer;
}
.seg + .seg { border-left: 1px solid var(--primary-color); }
.seg.active { background: var(--primary-color); color: var(--text-primary-color, #fff); }
.seg:disabled { opacity: 0.5; cursor: default; }
.vertices { grid-column: 1 / -1; display: flex; flex-direction: column; gap: 4px; max-height: 280px; overflow-y: auto; }
.vertex-row { display: grid; grid-template-columns: 22px 1fr 1fr 28px; gap: 6px; align-items: center; border-radius: 6px; }
.vertex-row.head { font-size: 12px; color: var(--secondary-text-color); }
.vertex-row.selected { background: color-mix(in srgb, #ff9800 18%, transparent); }
.vertex-index { font-size: 12px; color: var(--secondary-text-color); text-align: center; }
.fields .vertex-row input { font-size: 14px; padding: 4px 6px; }
.icon-btn {
  font: inherit;
  font-size: 16px;
  line-height: 1;
  width: 28px;
  height: 28px;
  padding: 0;
  border: none;
  border-radius: 14px;
  background: transparent;
  color: var(--secondary-text-color);
  cursor: pointer;
}
.icon-btn:hover:not(:disabled) { background: var(--secondary-background-color, #eee); color: var(--error-color, #db4437); }
.icon-btn:disabled { opacity: 0.3; cursor: default; }
.readout { font-size: 13px; color: var(--secondary-text-color); margin-top: 4px; }
.actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
.btn {
  font: inherit;
  font-size: 14px;
  padding: 7px 14px;
  border-radius: 18px;
  border: 1px solid var(--primary-color);
  background: transparent;
  color: var(--primary-color);
  cursor: pointer;
}
.btn.primary { background: var(--primary-color); color: var(--text-primary-color, #fff); }
.btn.danger { border-color: var(--error-color, #db4437); color: var(--error-color, #db4437); }
.btn:disabled { opacity: 0.5; cursor: default; }
.list { display: flex; flex-wrap: wrap; gap: 6px; }
.item {
  font: inherit;
  font-size: 14px;
  padding: 5px 12px;
  border-radius: 16px;
  border: 1px solid var(--divider-color, #ccc);
  background: var(--card-background-color, #fff);
  color: var(--primary-text-color);
  cursor: pointer;
}
.item.active { border-color: var(--primary-color); color: var(--primary-color); font-weight: 500; }
`;var Mt="http://www.w3.org/2000/svg",St=[.01,.05,.1,.25,.5],Y=["x","y","width","height"],Et={x:"x",y:"y",width:"Width",height:"Height"},Rt=400;function Lt(r){return r.kind==="rect"?{kind:"rect",rect:L({},r.rect)}:{kind:"polygon",ring:r.ring.slice()}}function ut(r){return r.kind==="rect"?r.rect:k(r.ring)}function Dt(r){return r.kind==="rect"?V(r.rect):r.ring}function _t(r,i){let t=(e,n)=>Math.abs(e-n)<5e-4;return t(r.x,i.x)&&t(r.y,i.y)&&t(r.width,i.width)&&t(r.height,i.height)}function u(r,i,t){let e=document.createElement(r);return i&&(e.className=i),t!==void 0&&(e.textContent=t),e}function g(r,i={}){let t=document.createElementNS(Mt,r);for(let e of Object.keys(i))t.setAttribute(e,String(i[e]));return t}function M(r){return String(Math.round(r*1e3)/1e3)}function q(r){return`${(Math.round(r*100)/100).toFixed(2)} m\xB2`}var T=class extends HTMLElement{constructor(){super();p(this,"hassObj");p(this,"narrowValue",!1);p(this,"root");p(this,"built",!1);p(this,"doc",null);p(this,"loadError",null);p(this,"unsubscribe",null);p(this,"subscribedVariant",null);p(this,"frameId",null);p(this,"variant","traced");p(this,"selected",null);p(this,"draft",null);p(this,"modePref",null);p(this,"vertex",null);p(this,"backup",null);p(this,"extraRings",0);p(this,"lastVertexDown",null);p(this,"dirty",!1);p(this,"step",.05);p(this,"status","");p(this,"busy",!1);p(this,"view",{x:0,y:0,width:8,height:6});p(this,"drag",null);p(this,"frameSelect");p(this,"variantSelect");p(this,"svg");p(this,"mapLayer");p(this,"draftLayer");p(this,"side");p(this,"menuButton");p(this,"inputs",{});p(this,"vertexInputs",[]);p(this,"vertexRows",[]);p(this,"areaReadout",null);p(this,"warning",null);p(this,"saveButton",null);this.root=this.attachShadow({mode:"open"})}set hass(t){let e=!this.hassObj;this.hassObj=t,this.menuButton&&(this.menuButton.hass=t),e&&this.render(),this.subscribe()}get hass(){return this.hassObj}set narrow(t){this.narrowValue=t,this.menuButton&&(this.menuButton.narrow=t),this.toggleAttribute("narrow",t)}get narrow(){return this.narrowValue}connectedCallback(){this.render(),this.subscribe()}disconnectedCallback(){this.stopSubscription()}subscribe(){let t=this.hassObj;if(!t||!this.isConnected||this.subscribedVariant===this.variant)return;this.stopSubscription(),this.subscribedVariant=this.variant;let e={type:"map_fusion/subscribe"};this.variant!=="traced"&&(e.variant=this.variant),this.unsubscribe=t.connection.subscribeMessage(n=>{this.doc=n,this.loadError=null,this.render()},e).catch(n=>{this.loadError=n&&n.code==="unknown_command"?"Map Fusion isn't loaded. Restart Home Assistant after installing it.":`Couldn't load the map: ${n&&n.message||String(n)}`,this.render()})}stopSubscription(){let t=this.unsubscribe;this.unsubscribe=null,this.subscribedVariant=null,t&&t.then(e=>{e&&e()}).catch(()=>{})}frames(){let t=this.doc?this.doc.frames.slice():[],e=this.hassObj&&this.hassObj.floors||{};for(let n of Object.keys(e))t.some(s=>s.frame_id===n)||t.push({frame_id:n,floor_id:n,name:`${e[n].name} (no vacuum map)`,bounds:null,areas:[],unmapped_rooms:[]});return t}frame(){let t=this.frames();return t.find(e=>e.frame_id===this.frameId)||t[0]||null}entries(t){let e=[];if(t)for(let s of t.areas)e.push({area_id:s.area_id,name:s.name,kind:s.origin,area:s});let n=this.doc?this.doc.unplaced_areas:[];for(let s of n)t&&t.floor_id&&s.floor_id&&s.floor_id!==t.floor_id||e.push({area_id:s.area_id,name:s.name,kind:"unplaced"});return e}entry(){return this.entries(this.frame()).find(t=>t.area_id===this.selected)||null}build(){this.root.innerHTML="";let t=u("style");t.textContent=ht;let e=u("div","toolbar");this.menuButton=document.createElement("ha-menu-button"),this.menuButton.hass=this.hassObj,this.menuButton.narrow=this.narrowValue;let n=u("div","title","Map Fusion");this.frameSelect=u("select","frame"),this.frameSelect.setAttribute("aria-label","Map"),this.frameSelect.addEventListener("change",()=>this.selectFrame(this.frameSelect.value)),this.variantSelect=u("select","variant"),this.variantSelect.setAttribute("aria-label","Shapes");for(let[l,d]of[["traced","Shapes as traced"],["filled","Furniture filled"]]){let o=u("option",void 0,d);o.value=l,this.variantSelect.append(o)}this.variantSelect.addEventListener("change",()=>{this.variant=this.variantSelect.value==="filled"?"filled":"traced",this.subscribe()}),e.append(this.menuButton,n,this.frameSelect,this.variantSelect);let s=u("div","body"),a=u("div","map-wrap");this.svg=g("svg",{class:"map",preserveAspectRatio:"xMidYMid meet",tabindex:0}),this.svg.setAttribute("role","img"),this.svg.setAttribute("aria-label","Map"),this.mapLayer=g("g"),this.draftLayer=g("g",{class:"draft-layer"}),this.svg.append(this.mapLayer,this.draftLayer),this.svg.addEventListener("pointerdown",l=>this.onPointerDown(l)),this.svg.addEventListener("pointermove",l=>this.onPointerMove(l)),this.svg.addEventListener("pointerup",l=>this.onPointerUp(l)),this.svg.addEventListener("pointercancel",l=>this.onPointerUp(l)),this.svg.addEventListener("keydown",l=>this.onKey(l)),a.append(this.svg),this.side=u("div","side"),s.append(a,this.side),this.root.append(t,e,s),this.built=!0}render(){if(!this.isConnected)return;this.built||this.build();let t=this.frames(),e=this.frame();e&&(this.frameId=e.frame_id),this.frameSelect.innerHTML="";for(let s of t){let a=u("option",void 0,s.name);a.value=s.frame_id,a.selected=s.frame_id===this.frameId,this.frameSelect.append(a)}this.frameSelect.hidden=t.length<2,this.variantSelect.value=this.variant;let n=this.entry();n?n.kind==="manual"&&!this.dirty&&n.area&&(this.draft=this.areaDraft(n.area)):(this.selected=null,this.draft=null,this.dirty=!1),this.vertex!==null&&(!this.draft||this.draft.kind!=="polygon"||this.vertex>=this.draft.ring.length)&&(this.vertex=null),this.renderMap(e),this.renderSide(e)}areaDraft(t){let e=t.polygons.filter(a=>a.length>=3),n=C(e);return this.extraRings=Math.max(0,e.length-1),(this.modePref||(n&&!j(t.polygons,t.rect)?"polygon":"rect"))==="polygon"&&n?{kind:"polygon",ring:R(n)}:{kind:"rect",rect:L({},t.rect)}}renderMap(t){let e=[];if(t){for(let o of t.areas)e.push(o.rect);for(let o of t.unmapped_rooms)e.push(o.rect)}this.draft&&e.push(ut(this.draft)),this.drag||(this.view=nt(e));let n=this.view;this.svg.setAttribute("viewBox",`${n.x} ${n.y} ${n.width} ${n.height}`);let s=this.mapLayer;s.innerHTML="";let a=g("g",{class:"grid"}),l=this.unitsPerPx()*11,d=n.width>30?5:n.width>15?2:1;for(let o=n.x;o<=n.x+n.width;o++)if(a.append(g("line",{x1:o,y1:n.y,x2:o,y2:n.y+n.height,class:o===0?"axis":""})),(o-n.x)%d===0&&o>n.x){let c=g("text",{x:o,y:n.y+l*1.2,class:"tick","font-size":l});c.textContent=String(o),a.append(c)}for(let o=n.y;o<=n.y+n.height;o++)if(a.append(g("line",{x1:n.x,y1:o,x2:n.x+n.width,y2:o,class:o===0?"axis":""})),(o-n.y)%d===0&&o>n.y){let c=g("text",{x:n.x+l*.3,y:o-l*.3,class:"tick","font-size":l});c.textContent=String(o),a.append(c)}if(s.append(a),!!t){for(let o of t.unmapped_rooms)s.append(g("path",{d:I(o.polygons),class:"unlinked"}));for(let o of t.areas){let c=["room",o.origin==="manual"?"manual":"",o.area_id===this.selected?"selected":""],h=o.area_id===this.selected&&this.draft,f=g("path",{d:I(o.polygons),class:c.join(" ")+(h?" ghost":"")});f.setAttribute("data-area",o.area_id);let m=g("title");m.textContent=o.name,f.append(m),s.append(f)}for(let o of t.areas){if(o.area_id===this.selected&&this.draft)continue;let c=g("text",{x:o.label_point[0],y:o.label_point[1],class:"label","font-size":l*1.15,"stroke-width":this.unitsPerPx()*3});c.textContent=o.name,s.append(c)}this.renderDraft()}}unitsPerPx(){let t=this.svg&&this.svg.clientWidth,e=this.svg&&this.svg.clientHeight;return!t||!e?this.view.width/800:Math.max(this.view.width/t,this.view.height/e)}renderDraft(){let t=this.draftLayer;t.innerHTML="";let e=this.draft;if(!e)return;let n=this.unitsPerPx(),s,a;if(e.kind==="rect"){let o=e.rect,c=g("rect",{x:o.x,y:o.y,width:o.width,height:o.height,class:"draft"});c.setAttribute("data-handle","move"),t.append(c);let h=n*12;for(let f of tt){let[m,y]=et(o,f),b=g("rect",{x:m-h/2,y:y-h/2,width:h,height:h,class:`handle handle-${f}`});b.setAttribute("data-handle",f),t.append(b)}s=[o.x+o.width/2,o.y+o.height/2],a=`${M(o.width)} \xD7 ${M(o.height)} m`}else{let o=e.ring,c=o.length,h=g("path",{d:I([o]),class:"draft"+(this.problem()?" invalid":"")});h.setAttribute("data-handle","move"),t.append(h);for(let m=0;m<c;m++){let y=o[m],b=o[(m+1)%c];if(Math.sqrt(Math.pow(b[0]-y[0],2)+Math.pow(b[1]-y[1],2))<n*28)continue;let H=g("circle",{cx:(y[0]+b[0])/2,cy:(y[1]+b[1])/2,r:n*4.5,class:"midpoint"});H.setAttribute("data-mid",String(m));let X=g("title");X.textContent="Drag or click to add a corner",H.append(X),t.append(H)}for(let m=0;m<c;m++){let y=o[m],b=g("circle",{cx:y[0],cy:y[1],r:n*6.5,class:"vertex"+(m===this.vertex?" selected":"")});b.setAttribute("data-vertex",String(m)),t.append(b)}let f=k(o);s=_(o),A(s[0],s[1],o)||(s=[f.x+f.width/2,f.y+f.height/2]),a=q(P(o))}let l=g("text",{x:s[0],y:s[1],class:"draft-label","font-size":n*13,"stroke-width":n*3});l.textContent=a,t.append(l);let d=this.entry();if(d){let o=g("text",{x:s[0],y:s[1]-n*16,class:"draft-label","font-size":n*13,"stroke-width":n*3});o.textContent=d.name,t.append(o)}}renderSide(t){let e=this.side;if(e.innerHTML="",this.inputs={},this.vertexInputs=[],this.vertexRows=[],this.areaReadout=null,this.warning=null,this.saveButton=null,this.loadError){e.append(u("div","error",this.loadError));return}if(!this.doc){e.append(u("div","hint","Loading the map\u2026"));return}if(!t){e.append(u("div","hint","No map yet. Link your vacuum's rooms to areas, or create a floor."));return}let n=this.entry();n?e.append(this.editor(n)):e.append(u("div","hint","Pick an area below, or click one on the map. Hand-placed and unplaced areas can be dragged into place."));let s=[["Not on the map yet",["unplaced"]],["Placed by hand",["manual"]],["From the vacuum map",["vacuum"]]],a=this.entries(t);for(let[l,d]of s){let o=a.filter(h=>d.indexOf(h.kind)!==-1);if(!o.length)continue;e.append(u("h3",void 0,l));let c=u("div","list");for(let h of o){let f=u("button","item"+(h.area_id===this.selected?" active":""),h.name);f.type="button",f.setAttribute("data-select",h.area_id),f.addEventListener("click",()=>this.select(h.area_id)),c.append(f)}e.append(c)}}editor(t){let e=u("div","editor");e.append(u("h2",void 0,t.name));let n={vacuum:"Shape from the vacuum map.",manual:"Placed by hand.",unplaced:"Not on the map yet."};if(e.append(u("div","hint",n[t.kind])),!this.draft){let c=u("div","actions");if(t.kind==="unplaced")c.append(this.button("Place on the map","place",!0,()=>this.startDraft({kind:"rect",rect:rt(this.bounds())})));else if(t.kind==="vacuum"&&t.area){let h=t.area;c.append(this.button("Replace with a rectangle","replace",!1,()=>this.startDraft({kind:"rect",rect:z(h.rect,.01)})),this.button("Replace with a polygon","replace-polygon",!1,()=>this.startDraft({kind:"polygon",ring:dt(h.polygons,h.rect)})))}return e.append(c),t.kind==="vacuum"&&e.append(u("div","hint small","To change which room this is, edit the vacuum's area links instead.")),e}let s=this.draft;if(t.kind==="manual"&&this.extraRings){let c=this.extraRings+1;e.append(u("div","warning",`This area has ${c} separate parts. Only the largest is edited here; saving drops the other ${c-1===1?"one":c-1}.`))}t.kind==="vacuum"&&e.append(u("div","warning","Saving replaces the vacuum's shape for this area. Remove the placement later to go back.")),e.append(this.modeToggle(s.kind)),e.append(u("div","hint small",s.kind==="rect"?"Drag the rectangle, a corner or an edge, or type below. Arrow keys move it; Shift + arrows resize.":"Drag a corner, or the whole shape. Click a dot on an edge to add a corner; double-click a corner (or select it and press Delete) to remove it. Shift while dragging lines a corner up with its neighbour."));let a=u("div","fields");if(s.kind==="rect")for(let c of Y){let h=u("label");h.append(u("span",void 0,`${Et[c]} (m)`));let f=this.numberInput(M(s.rect[c]));f.setAttribute("data-field",c),f.addEventListener("input",()=>this.onField(c,f.value)),h.append(f),a.append(h),this.inputs[c]=f}else a.append(this.vertexList(s.ring));let l=u("label");l.append(u("span",void 0,"Snap to"));let d=u("select");for(let c of St){let h=u("option",void 0,c<.1?`${Math.round(c*100)} cm`:`${c} m`);h.value=String(c),h.selected=c===this.step,d.append(h)}d.addEventListener("change",()=>{this.step=Number(d.value);for(let c of this.vertexInputs)for(let h of c)h.step=String(this.step);for(let c of Y){let h=this.inputs[c];h&&(h.step=String(this.step))}}),l.append(d),a.append(l),e.append(a),this.warning=u("div","warning"),e.append(this.warning),this.updateWarning();let o=u("div","actions");return this.saveButton=this.button("Save","save",!0,()=>this.save()),this.saveButton.disabled=!this.canSave(),o.append(this.saveButton),(t.kind!=="manual"||this.dirty)&&o.append(this.button(t.kind==="manual"?"Undo changes":"Cancel","cancel",!1,()=>this.cancel())),t.kind==="manual"&&o.append(this.button("Remove placement","remove",!1,()=>this.removePlacement(),!0)),e.append(o),this.status&&e.append(u("div","status",this.status)),e}numberInput(t){let e=u("input");return e.type="number",e.step=String(this.step),e.value=t,e}modeToggle(t){let e=u("div","segmented");e.setAttribute("role","group"),e.setAttribute("aria-label","Shape");let n=[["rect","Rectangle"],["polygon","Polygon"]];for(let[s,a]of n){let l=u("button","seg"+(s===t?" active":""),a);l.type="button",l.setAttribute("data-mode",s),l.setAttribute("aria-pressed",String(s===t)),l.disabled=this.busy,l.addEventListener("click",()=>this.setMode(s)),e.append(l)}return e}vertexList(t){let e=u("div","vertices"),n=u("div","vertex-row head");return n.append(u("span",void 0,"#"),u("span",void 0,"x (m)"),u("span",void 0,"y (m)"),u("span")),e.append(n),t.forEach((s,a)=>{let l=u("div","vertex-row"+(a===this.vertex?" selected":""));l.append(u("span","vertex-index",String(a+1)));let d=[];for(let c of[0,1]){let h=this.numberInput(M(s[c]));h.setAttribute(c?"data-vy":"data-vx",String(a)),h.setAttribute("aria-label",`Corner ${a+1} ${c?"y":"x"} (m)`),h.addEventListener("input",()=>this.onVertexField(a,c,h.value)),h.addEventListener("focus",()=>this.selectVertex(a)),l.append(h),d.push(h)}let o=u("button","icon-btn","\xD7");o.type="button",o.title="Remove this corner",o.setAttribute("aria-label",`Remove corner ${a+1}`),o.setAttribute("data-remove-vertex",String(a)),o.disabled=this.busy||t.length<=E,o.addEventListener("click",()=>this.deleteVertex(a)),l.append(o),e.append(l),this.vertexRows.push(l),this.vertexInputs.push([d[0],d[1]])}),this.areaReadout=u("div","readout",`${t.length} corners \xB7 ${q(P(t))}`),this.areaReadout.setAttribute("data-readout","area"),e.append(this.areaReadout),e}button(t,e,n,s,a=!1){let l=u("button","btn"+(n?" primary":"")+(a?" danger":""),t);return l.type="button",l.setAttribute("data-action",e),l.disabled=this.busy,l.addEventListener("click",s),l}bounds(){let t=this.frame();return t?t.bounds?t.bounds:N(t.areas.map(e=>e.rect)):null}problem(){return this.draft&&this.draft.kind==="polygon"?W(this.draft.ring):null}canSave(){return this.dirty&&!this.busy&&!this.problem()}updateWarning(){if(!this.warning||!this.draft)return;let t=this.frame(),e=ut(this.draft),n=Dt(this.draft),s=(t?t.areas:[]).filter(d=>d.area_id!==this.selected&&B(d.rect,e)>.01&&d.polygons.some(o=>ct(n,o))).map(d=>d.name),a=[],l=this.problem();l&&a.push(l),s.length&&a.push(`Overlaps ${s.join(", ")}.`),this.warning.textContent=a.join(" "),this.warning.hidden=!a.length}syncInputs(t){let e=this.draft;if(e){if(e.kind==="rect")for(let n of Y){let s=this.inputs[n];s&&n!==t&&(s.value=M(e.rect[n]))}else{if(this.vertexInputs.length!==e.ring.length){this.renderSide(this.frame());return}e.ring.forEach((n,s)=>{let a=this.vertexInputs[s];t!==`${s}:x`&&(a[0].value=M(n[0])),t!==`${s}:y`&&(a[1].value=M(n[1]))}),this.areaReadout&&(this.areaReadout.textContent=`${e.ring.length} corners \xB7 ${q(P(e.ring))}`)}this.saveButton&&(this.saveButton.disabled=!this.canSave()),this.updateWarning()}}highlightVertex(){this.renderDraft(),this.vertexRows.forEach((t,e)=>t.classList.toggle("selected",e===this.vertex))}resetEdit(){this.draft=null,this.dirty=!1,this.status="",this.modePref=null,this.vertex=null,this.backup=null,this.extraRings=0,this.lastVertexDown=null}selectFrame(t){if(!this.confirmDiscard()){this.frameSelect.value=this.frameId||"";return}this.frameId=t,this.selected=null,this.resetEdit(),this.render()}select(t){t!==this.selected&&this.confirmDiscard()&&(this.selected=t,this.resetEdit(),this.render())}confirmDiscard(){return this.dirty?typeof window.confirm!="function"||window.confirm("Discard the unsaved changes?"):!0}startDraft(t){this.draft=t,this.modePref=t.kind,this.vertex=null,this.dirty=!0,this.status="",this.render()}cancel(){this.resetEdit(),this.render()}setMode(t){let e=this.draft;if(!(!e||e.kind===t)){if(this.modePref=t,this.vertex=null,e.kind==="rect"){let n=this.backup&&_t(k(this.backup),e.rect)?this.backup:null;this.draft={kind:"polygon",ring:n||V(e.rect)},this.status=n?"The outline is back.":"",this.backup=null}else{let n=k(e.ring);this.draft={kind:"rect",rect:n},j([e.ring],n)?this.status="":(this.backup=e.ring,this.dirty=!0,this.status="Now the rectangle around the outline, so its detail is lost. Switch back to Polygon before changing anything to get it back.")}this.render()}}update(t,e){return this.draft&&JSON.stringify(t)===JSON.stringify(this.draft)?!1:(this.draft=t,this.dirty=!0,this.status="",this.renderDraft(),this.syncInputs(e),!0)}onField(t,e){let n=this.draft;if(!n||n.kind!=="rect")return;let s=Number(e);e===""||!isFinite(s)||(t==="width"||t==="height")&&s<=0||this.update({kind:"rect",rect:J(L({},n.rect),{[t]:s})},t)}onVertexField(t,e,n){let s=this.draft;if(!s||s.kind!=="polygon"||t>=s.ring.length)return;let a=Number(n);if(n===""||!isFinite(a))return;let l=s.ring[t];this.update({kind:"polygon",ring:G(s.ring,t,e?[l[0],a]:[a,l[1]])},`${t}:${e?"y":"x"}`)}selectVertex(t){this.vertex!==t&&(this.vertex=t,this.highlightVertex())}deleteVertex(t){let e=this.draft;if(!(!e||e.kind!=="polygon")){if(e.ring.length<=E){this.status=`A polygon needs at least ${E} corners.`,this.render();return}this.vertex=null,this.update({kind:"polygon",ring:at(e.ring,t)})}}save(){return O(this,null,function*(){let t=this.hassObj,e=this.frame(),n=this.draft;if(!t||!e||!n||!this.selected||this.problem())return;let s={type:"map_fusion/area/set",frame_id:e.frame_id,area_id:this.selected};n.kind==="rect"?s.rect=n.rect:s.polygons=[R(n.ring)],this.busy=!0,this.status="Saving\u2026",this.render();try{yield t.callWS(s),this.dirty=!1,this.backup=null,this.status="Saved."}catch(a){let l=a;this.status=`Couldn't save: ${l&&l.message||String(a)}`}this.busy=!1,this.render()})}removePlacement(){return O(this,null,function*(){let t=this.hassObj,e=this.frame();if(!(!t||!e||!this.selected)){this.busy=!0,this.render();try{yield t.callWS({type:"map_fusion/area/clear",frame_id:e.frame_id,area_id:this.selected}),this.resetEdit()}catch(n){let s=n;this.status=`Couldn't remove: ${s&&s.message||String(n)}`}this.busy=!1,this.render()}})}toMap(t){return it(t.clientX,t.clientY,this.svg.getBoundingClientRect(),this.view)}beginDrag(t,e,n){t.preventDefault(),this.drag={handle:e,vertex:n,start:Lt(this.draft),from:this.toMap(t),pointerId:t.pointerId,moved:!1};try{this.svg.setPointerCapture(t.pointerId)}catch(s){}try{this.svg.focus()}catch(s){}}onPointerDown(t){let e=t.target,n=this.draft,s=o=>e?e.getAttribute(o):null;if(n&&n.kind==="polygon"){let o=s("data-vertex");if(o!==null){let h=Number(o),f=Date.now(),m=this.lastVertexDown;if(m&&m.index===h&&f-m.time<Rt){t.preventDefault(),this.lastVertexDown=null,this.deleteVertex(h);return}this.lastVertexDown={index:h,time:f},this.beginDrag(t,"vertex",h),this.selectVertex(h);return}let c=s("data-mid");if(c!==null){let h=Number(c);this.lastVertexDown=null,this.vertex=h+1,this.update({kind:"polygon",ring:ot(n.ring,h)}),this.beginDrag(t,"vertex",h+1);return}}let a=s("data-handle");if(a&&n){this.lastVertexDown=null,this.beginDrag(t,a,-1),this.vertex!==null&&this.selectVertex(null);return}let l=s("data-area");if(l){this.select(l);return}let d=this.frame();if(d){let[o,c]=this.toMap(t),h=d.areas.find(f=>f.polygons.some(m=>A(o,c,m)));h&&this.select(h.area_id)}}onPointerMove(t){let e=this.drag;if(!e||t.pointerId!==e.pointerId)return;let[n,s]=this.toMap(t),a=n-e.from[0],l=s-e.from[1],d=e.start,o;d.kind==="rect"?o={kind:"rect",rect:$(d.rect,e.handle==="vertex"?"move":e.handle,a,l,this.step)}:e.handle==="vertex"?o={kind:"polygon",ring:U(d.ring,e.vertex,a,l,this.step,t.shiftKey)}:o={kind:"polygon",ring:K(d.ring,a,l,this.step)},this.update(o)&&(e.moved=!0)}onPointerUp(t){let e=this.drag;if(!(!e||t.pointerId!==e.pointerId)){this.drag=null,e.moved&&(this.lastVertexDown=null);try{this.svg.releasePointerCapture(t.pointerId)}catch(n){}this.render()}}onKey(t){let e=this.draft;if(!e)return;if(e.kind==="polygon"&&this.vertex!==null){if(t.key==="Delete"||t.key==="Backspace"){t.preventDefault(),this.deleteVertex(this.vertex);return}if(t.key==="Escape"){this.selectVertex(null);return}}let s={ArrowLeft:[-1,0],ArrowRight:[1,0],ArrowUp:[0,-1],ArrowDown:[0,1]}[t.key];if(!s)return;t.preventDefault();let a=s[0]*this.step,l=s[1]*this.step;e.kind==="rect"?this.update({kind:"rect",rect:$(e.rect,t.shiftKey?"se":"move",a,l,this.step)}):this.vertex!==null?this.update({kind:"polygon",ring:U(e.ring,this.vertex,a,l,this.step)}):this.update({kind:"polygon",ring:K(e.ring,a,l,this.step)})}};try{customElements.get("map-fusion-panel")||customElements.define("map-fusion-panel",T)}catch(r){console.error("map-fusion-panel: could not define the element",r)}console.info("%c MAP-FUSION-PANEL %c v0.4.0 ","color:#fff;background:#03a9f4;font-weight:700;","color:#03a9f4;background:#fff;font-weight:700;");
