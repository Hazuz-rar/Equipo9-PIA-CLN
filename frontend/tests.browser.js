'use strict';
(() => {
  const F=window.HotelForms;
  const examples=Array.from({length:10},(_,i)=>`00000000-0000-4000-8000-${(i+1).toString(16).padStart(12,'0')}`);
  const good=JSON.stringify({currency:'MXN',bar_by_room_and_season:{'Estándar|baja':1250},weekend_multiplier:1.2,channel_multipliers:{directo:1},customer_multipliers:{individual:1},seasons:[{name:'baja',start:'2026-12-01',end:'2026-12-31'}]});
  const tests=[
    ['UUID válido',()=>F.validUUID(examples[0])],
    ['UUID inválido rechazado',()=>!F.validUUID('abc')],
    ['Fechas coherentes',()=>F.dates('2026-12-10','2026-12-13').check_out==='2026-12-13'],
    ['Fechas inversas rechazadas',()=>fails(()=>F.dates('2026-12-13','2026-12-10'))],
    ['Grupo con 10 habitaciones',()=>F.roomIds(examples.join(',')).length===10],
    ['Grupo con 9 habitaciones rechazado',()=>fails(()=>F.roomIds(examples.slice(0,9).join(',')))],
    ['Grupo con duplicados rechazado',()=>fails(()=>F.roomIds(Array(10).fill(examples[0]).join(',')))],
    ['Importe con dos decimales',()=>F.amount('120.50')==='120.50'],
    ['Importe negativo rechazado',()=>fails(()=>F.amount('-1'))],
    ['Importe con 3 decimales rechazado',()=>fails(()=>F.amount('1.234'))],
    ['Diferencia tarifaria cero permitida',()=>F.amount('0','Diferencia',true)==='0'],
    ['Fecha/hora con zona',()=>/Z$/.test(F.localDateTimeISO('2026-12-10T15:30'))],
    ['Tarifa: JSON con estructura válida',()=>F.objectJSON(good).currency==='MXN'],
    ['Tarifa: JSON inválido rechazado',()=>fails(()=>F.objectJSON('{'))],
    ['Tarifa: sin temporada rechazada',()=>fails(()=>F.objectJSON('{}'))]
  ];
  function fails(f){try{f();return false;}catch{return true;}}
  let passed=0;const root=document.getElementById('results');root.replaceChildren();
  const title=document.createElement('h2');root.append(title);
  const list=document.createElement('ul');list.style.lineHeight='2';root.append(list);
  for(const [label,fn] of tests){let ok=false;try{ok=!!fn();}catch{}if(ok)passed++;
    const li=document.createElement('li');li.textContent=`${ok?'✓':'✗'} ${label}`;li.style.color=ok?'#176b50':'#b53e43';list.append(li);
  }
  title.textContent=`${passed}/${tests.length} pruebas unitarias aprobadas`;
})();
