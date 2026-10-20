/*! map-fusion-panel v0.4.0 built from frontend/src, do not edit */
var V=Object.defineProperty,j=Object.defineProperties;var C=Object.getOwnPropertyDescriptors;var L=Object.getOwnPropertySymbols;var N=Object.prototype.hasOwnProperty,$=Object.prototype.propertyIsEnumerable;var y=(a,n,t)=>n in a?V(a,n,{enumerable:!0,configurable:!0,writable:!0,value:t}):a[n]=t,g=(a,n)=>{for(var t in n||(n={}))N.call(n,t)&&y(a,t,n[t]);if(L)for(var t of L(n))$.call(n,t)&&y(a,t,n[t]);return a},R=(a,n)=>j(a,C(n));var u=(a,n,t)=>y(a,typeof n!="symbol"?n+"":n,t);var w=(a,n,t)=>new Promise((e,i)=>{var s=c=>{try{o(t.next(c))}catch(r){i(r)}},d=c=>{try{o(t.throw(c))}catch(r){i(r)}},o=c=>c.done?e(c.value):Promise.resolve(c.value).then(s,d);o((t=t.apply(a,n)).next())});var P=["nw","n","ne","e","se","s","sw","w"];function v(a,n){let t=n>0?Math.round(a/n)*n:a;return Math.round(t*1e3)/1e3}function H(a,n){return{x:v(a.x,n),y:v(a.y,n),width:v(a.width,n),height:v(a.height,n)}}function k(a,n,t,e,i){if(n==="move")return{x:v(a.x+t,i),y:v(a.y+e,i),width:a.width,height:a.height};let s=a.x,d=a.y,o=a.x+a.width,c=a.y+a.height,r=Math.max(.1,i);n.indexOf("w")!==-1&&(s=Math.min(v(s+t,i),o-r)),n.indexOf("e")!==-1&&(o=Math.max(v(o+t,i),s+r)),n.indexOf("n")!==-1&&(d=Math.min(v(d+e,i),c-r)),n.indexOf("s")!==-1&&(c=Math.max(v(c+e,i),d+r));let h=p=>Math.round(p*1e3)/1e3;return{x:h(s),y:h(d),width:h(o-s),height:h(c-d)}}function A(a,n){let t=n.indexOf("w")!==-1?a.x:n.indexOf("e")!==-1?a.x+a.width:a.x+a.width/2,e=n.indexOf("n")!==-1?a.y:n.indexOf("s")!==-1?a.y+a.height:a.y+a.height/2;return[t,e]}function I(a,n=3,t=3){return a?{x:Math.round((a.x+a.width+.5)*10)/10,y:Math.round(a.y*10)/10,width:n,height:t}:{x:0,y:0,width:n,height:t}}function S(a){if(!a.length)return null;let n=1/0,t=1/0,e=-1/0,i=-1/0;for(let s of a)n=Math.min(n,s.x),t=Math.min(t,s.y),e=Math.max(e,s.x+s.width),i=Math.max(i,s.y+s.height);return{x:n,y:t,width:e-n,height:i-t}}function F(a,n){let t=Math.min(a.x+a.width,n.x+n.width)-Math.max(a.x,n.x),e=Math.min(a.y+a.height,n.y+n.height)-Math.max(a.y,n.y);return t>0&&e>0?t*e:0}function T(a){let n=S(a)||{x:0,y:0,width:8,height:6},t=Math.floor(n.x-1),e=Math.floor(n.y-1),i=Math.ceil(n.x+n.width+1),s=Math.ceil(n.y+n.height+1);return{x:t,y:e,width:i-t,height:s-e}}function z(a,n,t){let e=!1;for(let i=0,s=t.length-1;i<t.length;s=i++){let[d,o]=t[i],[c,r]=t[s];o>n!=r>n&&a<(c-d)*(n-o)/(r-o)+d&&(e=!e)}return e}function E(a){let n=t=>t.toFixed(3);return a.filter(t=>t.length>=3).map(t=>"M"+t.map(e=>`${n(e[0])} ${n(e[1])}`).join(" L")+" Z").join(" ")}function D(a,n){if(a.length!==1||a[0].length!==4)return!1;let t=(e,i)=>Math.abs(e-i)<.002;return a[0].every(([e,i])=>(t(e,n.x)||t(e,n.x+n.width))&&(t(i,n.y)||t(i,n.y+n.height)))}function O(a,n,t,e){let i=Math.min(t.width/e.width,t.height/e.height)||1,s=(t.width-e.width*i)/2,d=(t.height-e.height*i)/2;return[e.x+(a-t.left-s)/i,e.y+(n-t.top-d)/i]}var B=`
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
`;var G="http://www.w3.org/2000/svg",K=[.01,.05,.1,.25,.5],M=["x","y","width","height"],W={x:"x",y:"y",width:"Width",height:"Height"};function l(a,n,t){let e=document.createElement(a);return n&&(e.className=n),t!==void 0&&(e.textContent=t),e}function f(a,n={}){let t=document.createElementNS(G,a);for(let e of Object.keys(n))t.setAttribute(e,String(n[e]));return t}function b(a){return String(Math.round(a*1e3)/1e3)}var x=class extends HTMLElement{constructor(){super();u(this,"hassObj");u(this,"narrowValue",!1);u(this,"root");u(this,"built",!1);u(this,"doc",null);u(this,"loadError",null);u(this,"unsubscribe",null);u(this,"subscribedVariant",null);u(this,"frameId",null);u(this,"variant","traced");u(this,"selected",null);u(this,"draft",null);u(this,"dirty",!1);u(this,"step",.05);u(this,"status","");u(this,"busy",!1);u(this,"view",{x:0,y:0,width:8,height:6});u(this,"drag",null);u(this,"frameSelect");u(this,"variantSelect");u(this,"svg");u(this,"mapLayer");u(this,"draftLayer");u(this,"side");u(this,"menuButton");u(this,"inputs",{});u(this,"warning",null);u(this,"saveButton",null);this.root=this.attachShadow({mode:"open"})}set hass(t){let e=!this.hassObj;this.hassObj=t,this.menuButton&&(this.menuButton.hass=t),e&&this.render(),this.subscribe()}get hass(){return this.hassObj}set narrow(t){this.narrowValue=t,this.menuButton&&(this.menuButton.narrow=t),this.toggleAttribute("narrow",t)}get narrow(){return this.narrowValue}connectedCallback(){this.render(),this.subscribe()}disconnectedCallback(){this.stopSubscription()}subscribe(){let t=this.hassObj;if(!t||!this.isConnected||this.subscribedVariant===this.variant)return;this.stopSubscription(),this.subscribedVariant=this.variant;let e={type:"map_fusion/subscribe"};this.variant!=="traced"&&(e.variant=this.variant),this.unsubscribe=t.connection.subscribeMessage(i=>{this.doc=i,this.loadError=null,this.render()},e).catch(i=>{this.loadError=i&&i.code==="unknown_command"?"Map Fusion isn't loaded. Restart Home Assistant after installing it.":`Couldn't load the map: ${i&&i.message||String(i)}`,this.render()})}stopSubscription(){let t=this.unsubscribe;this.unsubscribe=null,this.subscribedVariant=null,t&&t.then(e=>{e&&e()}).catch(()=>{})}frames(){let t=this.doc?this.doc.frames.slice():[],e=this.hassObj&&this.hassObj.floors||{};for(let i of Object.keys(e))t.some(s=>s.frame_id===i)||t.push({frame_id:i,floor_id:i,name:`${e[i].name} (no vacuum map)`,bounds:null,areas:[],unmapped_rooms:[]});return t}frame(){let t=this.frames();return t.find(e=>e.frame_id===this.frameId)||t[0]||null}entries(t){let e=[];if(t)for(let s of t.areas)e.push({area_id:s.area_id,name:s.name,kind:s.origin,area:s});let i=this.doc?this.doc.unplaced_areas:[];for(let s of i)t&&t.floor_id&&s.floor_id&&s.floor_id!==t.floor_id||e.push({area_id:s.area_id,name:s.name,kind:"unplaced"});return e}entry(){return this.entries(this.frame()).find(t=>t.area_id===this.selected)||null}build(){this.root.innerHTML="";let t=l("style");t.textContent=B;let e=l("div","toolbar");this.menuButton=document.createElement("ha-menu-button"),this.menuButton.hass=this.hassObj,this.menuButton.narrow=this.narrowValue;let i=l("div","title","Map Fusion");this.frameSelect=l("select","frame"),this.frameSelect.setAttribute("aria-label","Map"),this.frameSelect.addEventListener("change",()=>this.selectFrame(this.frameSelect.value)),this.variantSelect=l("select","variant"),this.variantSelect.setAttribute("aria-label","Shapes");for(let[o,c]of[["traced","Shapes as traced"],["filled","Furniture filled"]]){let r=l("option",void 0,c);r.value=o,this.variantSelect.append(r)}this.variantSelect.addEventListener("change",()=>{this.variant=this.variantSelect.value==="filled"?"filled":"traced",this.subscribe()}),e.append(this.menuButton,i,this.frameSelect,this.variantSelect);let s=l("div","body"),d=l("div","map-wrap");this.svg=f("svg",{class:"map",preserveAspectRatio:"xMidYMid meet",tabindex:0}),this.svg.setAttribute("role","img"),this.svg.setAttribute("aria-label","Map"),this.mapLayer=f("g"),this.draftLayer=f("g",{class:"draft-layer"}),this.svg.append(this.mapLayer,this.draftLayer),this.svg.addEventListener("pointerdown",o=>this.onPointerDown(o)),this.svg.addEventListener("pointermove",o=>this.onPointerMove(o)),this.svg.addEventListener("pointerup",o=>this.onPointerUp(o)),this.svg.addEventListener("pointercancel",o=>this.onPointerUp(o)),this.svg.addEventListener("keydown",o=>this.onKey(o)),d.append(this.svg),this.side=l("div","side"),s.append(d,this.side),this.root.append(t,e,s),this.built=!0}render(){if(!this.isConnected)return;this.built||this.build();let t=this.frames(),e=this.frame();e&&(this.frameId=e.frame_id),this.frameSelect.innerHTML="";for(let s of t){let d=l("option",void 0,s.name);d.value=s.frame_id,d.selected=s.frame_id===this.frameId,this.frameSelect.append(d)}this.frameSelect.hidden=t.length<2,this.variantSelect.value=this.variant;let i=this.entry();i?i.kind==="manual"&&!this.dirty&&i.area&&(this.draft=g({},i.area.rect)):(this.selected=null,this.draft=null,this.dirty=!1),this.renderMap(e),this.renderSide(e)}renderMap(t){let e=[];if(t){for(let r of t.areas)e.push(r.rect);for(let r of t.unmapped_rooms)e.push(r.rect)}this.draft&&e.push(this.draft),this.drag||(this.view=T(e));let i=this.view;this.svg.setAttribute("viewBox",`${i.x} ${i.y} ${i.width} ${i.height}`);let s=this.mapLayer;s.innerHTML="";let d=f("g",{class:"grid"}),o=this.unitsPerPx()*11,c=i.width>30?5:i.width>15?2:1;for(let r=i.x;r<=i.x+i.width;r++)if(d.append(f("line",{x1:r,y1:i.y,x2:r,y2:i.y+i.height,class:r===0?"axis":""})),(r-i.x)%c===0&&r>i.x){let h=f("text",{x:r,y:i.y+o*1.2,class:"tick","font-size":o});h.textContent=String(r),d.append(h)}for(let r=i.y;r<=i.y+i.height;r++)if(d.append(f("line",{x1:i.x,y1:r,x2:i.x+i.width,y2:r,class:r===0?"axis":""})),(r-i.y)%c===0&&r>i.y){let h=f("text",{x:i.x+o*.3,y:r-o*.3,class:"tick","font-size":o});h.textContent=String(r),d.append(h)}if(s.append(d),!!t){for(let r of t.unmapped_rooms)s.append(f("path",{d:E(r.polygons),class:"unlinked"}));for(let r of t.areas){let h=["room",r.origin==="manual"?"manual":"",r.area_id===this.selected?"selected":""],p=r.area_id===this.selected&&this.draft,m=f("path",{d:E(r.polygons),class:h.join(" ")+(p?" ghost":"")});m.setAttribute("data-area",r.area_id);let _=f("title");_.textContent=r.name,m.append(_),s.append(m)}for(let r of t.areas){if(r.area_id===this.selected&&this.draft)continue;let h=f("text",{x:r.label_point[0],y:r.label_point[1],class:"label","font-size":o*1.15,"stroke-width":this.unitsPerPx()*3});h.textContent=r.name,s.append(h)}this.renderDraft()}}unitsPerPx(){let t=this.svg&&this.svg.clientWidth,e=this.svg&&this.svg.clientHeight;return!t||!e?this.view.width/800:Math.max(this.view.width/t,this.view.height/e)}renderDraft(){let t=this.draftLayer;t.innerHTML="";let e=this.draft;if(!e)return;let i=this.unitsPerPx(),s=f("rect",{x:e.x,y:e.y,width:e.width,height:e.height,class:"draft"});s.setAttribute("data-handle","move"),t.append(s);let d=i*12;for(let r of P){let[h,p]=A(e,r),m=f("rect",{x:h-d/2,y:p-d/2,width:d,height:d,class:`handle handle-${r}`});m.setAttribute("data-handle",r),t.append(m)}let o=f("text",{x:e.x+e.width/2,y:e.y+e.height/2,class:"draft-label","font-size":i*13,"stroke-width":i*3});o.textContent=`${b(e.width)} \xD7 ${b(e.height)} m`,t.append(o);let c=this.entry();if(c){let r=f("text",{x:e.x+e.width/2,y:e.y+e.height/2-i*16,class:"draft-label","font-size":i*13,"stroke-width":i*3});r.textContent=c.name,t.append(r)}}renderSide(t){let e=this.side;if(e.innerHTML="",this.inputs={},this.warning=null,this.saveButton=null,this.loadError){e.append(l("div","error",this.loadError));return}if(!this.doc){e.append(l("div","hint","Loading the map\u2026"));return}if(!t){e.append(l("div","hint","No map yet. Link your vacuum's rooms to areas, or create a floor."));return}let i=this.entry();i?e.append(this.editor(i)):e.append(l("div","hint","Pick an area below, or click one on the map. Hand-placed and unplaced areas can be dragged into place."));let s=[["Not on the map yet",["unplaced"]],["Placed by hand",["manual"]],["From the vacuum map",["vacuum"]]],d=this.entries(t);for(let[o,c]of s){let r=d.filter(p=>c.indexOf(p.kind)!==-1);if(!r.length)continue;e.append(l("h3",void 0,o));let h=l("div","list");for(let p of r){let m=l("button","item"+(p.area_id===this.selected?" active":""),p.name);m.type="button",m.setAttribute("data-select",p.area_id),m.addEventListener("click",()=>this.select(p.area_id)),h.append(m)}e.append(h)}}editor(t){let e=l("div","editor");e.append(l("h2",void 0,t.name));let i={vacuum:"Shape from the vacuum map.",manual:"Placed by hand. Drag it, its corners or edges, or type below.",unplaced:"Not on the map yet."};if(e.append(l("div","hint",i[t.kind])),!this.draft){let r=l("div","actions");if(t.kind==="unplaced")r.append(this.button("Place on the map","place",!0,()=>this.startDraft(I(this.bounds()))));else if(t.kind==="vacuum"&&t.area){let h=t.area;r.append(this.button("Replace with a rectangle","replace",!1,()=>this.startDraft(H(h.rect,.01))))}return e.append(r),t.kind==="vacuum"&&e.append(l("div","hint small","To change which room this is, edit the vacuum's area links instead.")),e}t.kind==="manual"&&t.area&&!D(t.area.polygons,t.area.rect)&&e.append(l("div","warning","This area has a polygon shape; saving here turns it into a rectangle.")),t.kind==="vacuum"&&e.append(l("div","warning","Saving replaces the vacuum's shape for this area. Remove the placement later to go back."));let s=l("div","fields");for(let r of M){let h=l("label");h.append(l("span",void 0,`${W[r]} (m)`));let p=l("input");p.type="number",p.step=String(this.step),p.value=b(this.draft[r]),p.setAttribute("data-field",r),p.addEventListener("input",()=>this.onField(r,p.value)),h.append(p),s.append(h),this.inputs[r]=p}let d=l("label");d.append(l("span",void 0,"Snap to"));let o=l("select");for(let r of K){let h=l("option",void 0,r<.1?`${Math.round(r*100)} cm`:`${r} m`);h.value=String(r),h.selected=r===this.step,o.append(h)}o.addEventListener("change",()=>{this.step=Number(o.value);for(let r of M){let h=this.inputs[r];h&&(h.step=String(this.step))}}),d.append(o),s.append(d),e.append(s),this.warning=l("div","warning"),e.append(this.warning),this.updateWarning();let c=l("div","actions");return this.saveButton=this.button("Save","save",!0,()=>this.save()),this.saveButton.disabled=!this.dirty||this.busy,c.append(this.saveButton),(t.kind!=="manual"||this.dirty)&&c.append(this.button(t.kind==="manual"?"Undo changes":"Cancel","cancel",!1,()=>this.cancel())),t.kind==="manual"&&c.append(this.button("Remove placement","remove",!1,()=>this.removePlacement(),!0)),e.append(c),this.status&&e.append(l("div","status",this.status)),e}button(t,e,i,s,d=!1){let o=l("button","btn"+(i?" primary":"")+(d?" danger":""),t);return o.type="button",o.setAttribute("data-action",e),o.disabled=this.busy,o.addEventListener("click",s),o}bounds(){let t=this.frame();return t?t.bounds?t.bounds:S(t.areas.map(e=>e.rect)):null}updateWarning(){if(!this.warning||!this.draft)return;let t=this.frame(),e=this.draft,i=(t?t.areas:[]).filter(s=>s.area_id!==this.selected&&F(s.rect,e)>.01).map(s=>s.name);this.warning.textContent=i.length?`Overlaps ${i.join(", ")}.`:"",this.warning.hidden=!i.length}syncInputs(t){if(this.draft){for(let e of M){let i=this.inputs[e];i&&e!==t&&(i.value=b(this.draft[e]))}this.saveButton&&(this.saveButton.disabled=!this.dirty||this.busy),this.updateWarning()}}selectFrame(t){if(!this.confirmDiscard()){this.frameSelect.value=this.frameId||"";return}this.frameId=t,this.selected=null,this.draft=null,this.dirty=!1,this.status="",this.render()}select(t){t!==this.selected&&this.confirmDiscard()&&(this.selected=t,this.draft=null,this.dirty=!1,this.status="",this.render())}confirmDiscard(){return this.dirty?typeof window.confirm!="function"||window.confirm("Discard the unsaved changes?"):!0}startDraft(t){this.draft=t,this.dirty=!0,this.status="",this.render()}cancel(){this.draft=null,this.dirty=!1,this.status="",this.render()}onField(t,e){if(!this.draft)return;let i=Number(e);e===""||!isFinite(i)||(t==="width"||t==="height")&&i<=0||(this.draft=R(g({},this.draft),{[t]:i}),this.dirty=!0,this.status="",this.renderDraft(),this.syncInputs(t))}save(){return w(this,null,function*(){let t=this.hassObj,e=this.frame();if(!(!t||!e||!this.draft||!this.selected)){this.busy=!0,this.status="Saving\u2026",this.render();try{yield t.callWS({type:"map_fusion/area/set",frame_id:e.frame_id,area_id:this.selected,rect:this.draft}),this.dirty=!1,this.status="Saved."}catch(i){let s=i;this.status=`Couldn't save: ${s&&s.message||String(i)}`}this.busy=!1,this.render()}})}removePlacement(){return w(this,null,function*(){let t=this.hassObj,e=this.frame();if(!(!t||!e||!this.selected)){this.busy=!0,this.render();try{yield t.callWS({type:"map_fusion/area/clear",frame_id:e.frame_id,area_id:this.selected}),this.draft=null,this.dirty=!1,this.status=""}catch(i){let s=i;this.status=`Couldn't remove: ${s&&s.message||String(i)}`}this.busy=!1,this.render()}})}toMap(t){return O(t.clientX,t.clientY,this.svg.getBoundingClientRect(),this.view)}onPointerDown(t){let e=t.target,i=e&&e.getAttribute("data-handle");if(i&&this.draft){t.preventDefault(),this.drag={handle:i,start:g({},this.draft),from:this.toMap(t),pointerId:t.pointerId};try{this.svg.setPointerCapture(t.pointerId)}catch(o){}return}let s=e&&e.getAttribute("data-area");if(s){this.select(s);return}let d=this.frame();if(d){let[o,c]=this.toMap(t),r=d.areas.find(h=>h.polygons.some(p=>z(o,c,p)));r&&this.select(r.area_id)}}onPointerMove(t){let e=this.drag;if(!e||t.pointerId!==e.pointerId)return;let[i,s]=this.toMap(t);this.draft=k(e.start,e.handle,i-e.from[0],s-e.from[1],this.step),this.dirty=!0,this.status="",this.renderDraft(),this.syncInputs()}onPointerUp(t){if(!(!this.drag||t.pointerId!==this.drag.pointerId)){this.drag=null;try{this.svg.releasePointerCapture(t.pointerId)}catch(e){}this.render()}}onKey(t){if(!this.draft)return;let i={ArrowLeft:[-1,0],ArrowRight:[1,0],ArrowUp:[0,-1],ArrowDown:[0,1]}[t.key];if(!i)return;t.preventDefault();let s=t.shiftKey?"se":"move";this.draft=k(this.draft,s,i[0]*this.step,i[1]*this.step,this.step),this.dirty=!0,this.renderDraft(),this.syncInputs()}};try{customElements.get("map-fusion-panel")||customElements.define("map-fusion-panel",x)}catch(a){console.error("map-fusion-panel: could not define the element",a)}console.info("%c MAP-FUSION-PANEL %c v0.4.0 ","color:#fff;background:#03a9f4;font-weight:700;","color:#03a9f4;background:#fff;font-weight:700;");
