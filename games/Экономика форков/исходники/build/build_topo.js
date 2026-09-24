// Контуры: id → ISO3 (или null у территорий без данных), без Антарктиды; имена не нужны
const fs = require('fs');
const geomIso = require('/tmp/game/build/geom_iso.json');
for (const res of ['110m', '50m']) {
  const t = JSON.parse(fs.readFileSync('/tmp/geo/node_modules/world-atlas/countries-' + res + '.json', 'utf8'));
  const g = t.objects.countries.geometries.filter(x => x.id !== '010');
  g.forEach(x => { const k = x.id != null ? x.id : x.properties.name; x.id = geomIso[k] || null; if (!x.id) x.properties = { n: x.properties.name }; else delete x.properties; });
  t.objects.countries.geometries = g;
  delete t.objects.land;
  fs.writeFileSync('/tmp/game/build/topo' + res + '.json', JSON.stringify(t));
  console.log(res, g.length, 'геометрий,', JSON.stringify(t).length, 'байт; без данных:', g.filter(x => !x.id).map(x => x.properties.n).join(', '));
}
