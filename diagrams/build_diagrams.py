"""Generate offline SVG pipeline diagrams and equivalent editable Mermaid sources."""
from pathlib import Path
from html import escape

ROOT = Path(__file__).resolve().parent
COLORS = {'step':('#eff6ff','#2563eb'), 'decision':('#fff7ed','#d97706'),
          'error':('#fff1f2','#e11d48'), 'result':('#ecfdf5','#059669'),
          'note':('#f1f5f9','#64748b')}

def make(name, title, subtitle, nodes, edges, height):
    # nodes: id, x, y, title, supporting lines, kind. Every box is 300 x 94.
    by_id = {n[0]: n for n in nodes}
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="1240" height="{height}" viewBox="0 0 1240 {height}" role="img" aria-label="{escape(title)}">',
      '<defs><marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8" fill="none" stroke="#64748b" stroke-width="1.5"/></marker></defs>',
      '<rect width="100%" height="100%" fill="#ffffff"/>',
      '<style>text{font-family:Segoe UI,Arial,sans-serif}.title{font-size:27px;font-weight:700;fill:#0f172a}.sub{font-size:15px;fill:#475569}.node{font-size:17px;font-weight:650;fill:#0f172a}.detail{font-size:14px;fill:#334155}.edge{font-size:13px;font-weight:650;fill:#475569;paint-order:stroke;stroke:white;stroke-width:5px;stroke-linejoin:round}</style>',
      f'<text x="40" y="44" class="title">{escape(title)}</text>',
      f'<text x="40" y="74" class="sub">{escape(subtitle)}</text>']
    mermaid=['flowchart TD']
    for a,b,label,route in edges:
        na,nb=by_id[a],by_id[b]; ax,ay=na[1],na[2]; bx,by=nb[1],nb[2]
        if route=='down':
            sx,sy=ax+150,ay+94; tx,ty=bx+150,by
            mid=(sy+ty)/2; path=f'M{sx},{sy} C{sx},{mid} {tx},{mid} {tx},{ty}'
            lx,ly=(sx+tx)/2+10,mid-5
        elif route=='right':
            sx,sy=ax+300,ay+47;tx,ty=bx,by+47
            mid=(sx+tx)/2;path=f'M{sx},{sy} C{mid},{sy} {mid},{ty} {tx},{ty}'
            lx,ly=mid-15,(sy+ty)/2-10
        else:
            sx,sy=ax,ay+47;tx,ty=bx+300,by+47
            mid=(sx+tx)/2;path=f'M{sx},{sy} C{mid},{sy} {mid},{ty} {tx},{ty}'
            lx,ly=mid-25,(sy+ty)/2-10
        svg.append(f'<path d="{path}" fill="none" stroke="#64748b" stroke-width="2" marker-end="url(#arrow)"/>')
        if label: svg.append(f'<text x="{lx}" y="{ly}" class="edge">{escape(label)}</text>')
        mermaid.append(f'  {a} -->'+(f'|"{label}"|' if label else '')+f' {b}')
    for key,x,y,heading,lines,kind in nodes:
        fill,stroke=COLORS[kind]
        svg.append(f'<rect x="{x}" y="{y}" width="300" height="94" rx="14" fill="{fill}" stroke="{stroke}" stroke-width="1.6"/>')
        svg.append(f'<text x="{x+16}" y="{y+28}" class="node">{escape(heading)}</text>')
        for i,line in enumerate(lines): svg.append(f'<text x="{x+16}" y="{y+51+i*19}" class="detail">{escape(line)}</text>')
        label='<br/>'.join([heading]+lines).replace('"',"'")
        mermaid.append(f'  {key}["{label}"]:::{kind}')
    svg.append(f'<text x="40" y="{height-22}" class="sub">Atmosight 1.1.1 • Current implemented workflow • Blue: process · Amber: decision · Red: error · Green: output</text></svg>')
    for kind,(fill,stroke) in COLORS.items(): mermaid.append(f'  classDef {kind} fill:{fill},stroke:{stroke},color:#0f172a')
    (ROOT/f'{name}.svg').write_text('\n'.join(svg),encoding='utf-8')
    (ROOT/f'{name}.mmd').write_text('\n'.join(mermaid)+'\n',encoding='utf-8')
    return name,title

items=[]
items.append(make('01-upload-and-compatibility','01 / CSV upload and compatibility','Start here. File and configuration errors stop the request; quality findings are retained.',[
 ('upload',460,110,'Upload CSV',['UTF-8 / optional BOM','Up to 50 MB and 250,000 data rows'],'step'),
 ('file',460,270,'Readable, supported structure?',['Nonempty, unique headers','At least one observation'],'decision'),
 ('reject',900,270,'File rejected',['Encoding / parser / size / row limit','Fix the file, then upload again'],'error'),
 ('inspect',460,430,'Preview and profile all columns',['First 5 rows; missing/numeric values','Ranges, distributions and duplicates'],'step'),
 ('dates',40,430,'Dates / stations recognized?',['Yes: date quality and station gaps','No: those diagnostics are omitted'],'note'),
 ('map',460,590,'Confirm mapping and units',['Known aliases suggested','Unknown / ambiguous: map manually'],'step'),
 ('badmap',900,590,'Invalid mapping blocks analysis',['Duplicate source / missing column','AQI, labels or CO2 used as input'],'error'),
 ('mode',460,750,'Choose analysis mode',['Explicit quality-only, or no inputs?','Otherwise request classification'],'decision'),
 ('quality',40,750,'Quality-only route',['Profiles + originals + row errors','No air-quality predictions'],'result'),
 ('guards',460,910,'Daily data + supported units?',['Confirm daily observations','ug/m3 or mg/m3 mass concentrations'],'decision'),
 ('blocked',900,910,'Classification blocked',['Hourly / unknown interval or ppm','Correct config or choose quality-only'],'error'),
 ('next',460,1070,'Convert and validate each row',['CO → mg/m3; other pollutants → ug/m3','Continue to diagram 02'],'result'),
 ],[('upload','file','','down'),('file','reject','No','right'),('file','inspect','Yes','down'),('inspect','dates','If available','left'),('inspect','map','','down'),('map','badmap','Invalid','right'),('map','mode','Valid','down'),('mode','quality','Yes','left'),('mode','guards','Classification','down'),('guards','blocked','No','right'),('guards','next','Yes','down')],1230))

items.append(make('02-row-validation-and-model-selection','02 / Row validation and model selection','Each row follows its own route. A single CSV can use multiple models and contain invalid rows.',[
 ('row',460,110,'Read one original row',['Apply confirmed mapping','Recognize blanks / NA / null as missing'],'step'),
 ('valid',460,270,'Are mapped readings valid?',['Numeric, nonnegative and finite','Within model numeric bounds'],'decision'),
 ('error',900,270,'Keep row with an error',['Also: extra cells or all inputs missing','Skip its prediction; other rows continue'],'error'),
 ('six',460,430,'All six pollutants observed?',['PM2.5, PM10, SO2, NO2, CO, O3','Check values, not just column names'],'decision'),
 ('baseline',900,430,'Six-pollutant baseline',['Use all six measured inputs','No missing-input imputation needed'],'result'),
 ('pair',460,590,'PM2.5 and PM10 observed?',['Dedicated pair artifact installed?','Both conditions must be satisfied'],'decision'),
 ('pairmodel',900,590,'PM2.5 + PM10 model',['Uses these two inputs only','Warn about extra ignored pollutants'],'result'),
 ('single',460,750,'PM2.5 observed?',['Dedicated single artifact installed?','Both conditions must be satisfied'],'decision'),
 ('singlemodel',900,750,'PM2.5-only model',['Uses PM2.5 only','Warn about extra ignored pollutants'],'result'),
 ('fallback',460,910,'Baseline imputation fallback',['At least one other valid input exists','Fill missing inputs with training medians'],'result'),
 ('missing',40,590,'Blank is different from invalid',['Missing input may change the model','Bad mapped values reject the row'],'note'),
 ('quality',40,910,'Quality-only exception',['No model selection or imputation','Mapped bad values can still yield errors'],'note'),
 ('next',460,1070,'Collect row outcomes',['Predicted rows + preserved errors','Continue to diagram 03'],'step'),
 ],[('row','valid','','down'),('valid','error','No','right'),('valid','six','Yes','down'),('six','baseline','Yes','right'),('six','pair','No','down'),('pair','pairmodel','Yes','right'),('pair','single','No','down'),('single','singlemodel','Yes','right'),('single','fallback','No','down'),('fallback','next','','down')],1230))

items.append(make('03-results-explanations-and-exports','03 / Results, explanations and exports','Every selected-model route in diagram 02 enters prediction here. Invalid rows remain in the report.',[
 ('predict',460,110,'Run the selected model',['Category + class probabilities','Model identity and evaluation evidence'],'step'),
 ('warn',460,270,'Add quality and anomaly notes',['Missing / ignored inputs; high values','PM2.5 > PM10; Isolation Forest flag'],'step'),
 ('continue',40,270,'Warning does not reject a row',['Unusual readings still get predictions','Probability is not a calibrated guarantee'],'note'),
 ('batch',460,430,'Assemble batch results',['Counts, paged rows and original data','Completeness, errors and compatibility'],'step'),
 ('reference',900,430,'Recognized reference labels?',['Yes: agreement, macro F1 and matrix','No: skip reference evaluation'],'decision'),
 ('explain',460,590,'Want a row explanation?',['Open a classified row in Classify','Run classification to calculate SHAP'],'decision'),
 ('shap',900,590,'Single-row explanation',['SHAP factors for the selected model','Batch itself omits SHAP for speed'],'result'),
 ('quality',40,430,'Quality-only report joins here',['No categories, probabilities or SHAP','Profiles, original rows and errors remain'],'result'),
 ('exports',460,750,'Export results',['Choose full report or measurements','Export does not retrain the model'],'decision'),
 ('json',40,910,'Complete report: JSON',['Originals, errors, quality, configuration','Predictions and reference metrics if any'],'result'),
 ('csv',460,910,'Converted measurements: CSV',['Classification mode only; canonical units','Missing stays blank; errors are retained'],'result'),
 ('history',900,910,'Optional single-row history',['Single classification uses local history','Batch is not a persistent dataset archive'],'note'),
 ('service',40,110,'Backend / model failure',['Show request error; retry after fixing','No simulated prediction fallback'],'error'),
 ('end',460,1070,'End: inspect or export evidence',['No online learning or regional adaptation','No automatic aggregation or forecasting'],'note'),
 ],[('predict','warn','','down'),('predict','service','Failure','left'),('warn','continue','Review','left'),('warn','batch','','down'),('quality','batch','','right'),('batch','reference','If labels exist','right'),('batch','explain','','down'),('explain','shap','Yes','right'),('explain','exports','Continue','down'),('exports','json','Full report','left'),('exports','csv','Measurements','down'),('csv','end','','down')],1230))

html='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Atmosight CSV pipeline diagrams</title><style>body{margin:0;background:#eef2f6;color:#0f172a;font:16px Segoe UI,Arial,sans-serif}header,main{max-width:1240px;margin:auto;padding:28px}h1{margin:0 0 12px}nav{display:flex;gap:20px;flex-wrap:wrap}a{color:#1d4ed8}section{margin:24px 0;background:white;border-radius:16px;overflow:hidden;box-shadow:0 3px 18px #0f172a10}img{width:100%;height:auto;display:block}.note{line-height:1.6;max-width:1000px}.links{padding:16px;border-top:1px solid #e2e8f0}@media print{body{background:white}header{padding:10px}section{break-before:page;box-shadow:none}main{padding:0}.links{display:none}}</style><header><h1>Atmosight: from CSV to results</h1><p class="note">Three diagrams cover upload checks, per-row model selection, and final evidence. Read top to bottom. Colored boxes distinguish processes, decisions, errors and outputs. These diagrams describe the implemented 1.1.1 app.</p><nav>'''
html+=''.join(f'<a href="#{name}">{escape(title)}</a>' for name,title in items)+'</nav></header><main>'
for name,title in items:
    html+=f'<section id="{name}"><img src="{name}.svg" alt="{escape(title)}"><div class="links"><a href="{name}.svg">Open SVG diagram</a> · <a href="{name}.mmd">Editable Mermaid source</a></div></section>'
html+='''<p class="note"><strong>Reading the branches:</strong> Every selected model in diagram 02 proceeds to diagram 03. Invalid rows are retained and skipped; they do not stop other valid rows. Quality-only analysis does not run models, but invalid mapped measurements can still generate row errors. Reference metrics use only predicted rows with exact recognized category labels; macro F1 includes all six classes, including absent-class zeros. A quality-only dataset with no pollutant mappings can contain valid negative values such as temperatures.</p><p class="note"><strong>File errors versus warnings:</strong> File/configuration errors require correction and resubmission. Duplicate observations, date gaps, screening ceilings and anomaly flags are reported without automatic removal. Date/station diagnostics require recognized column names and parseable ISO dates; there is no timezone conversion or gap filling. A missing specialist model falls through to the next supported route; a model loading/inference failure may fail the analysis request.</p></main></html>'''
(ROOT/'index.html').write_text(html,encoding='utf-8')
(ROOT/'README.md').write_text('# Atmosight CSV pipeline diagrams\n\nOpen `index.html` in a browser for all three diagrams. Everything is local; no internet connection or Mermaid installation is required. Each SVG is a scalable standalone diagram. Each `.mmd` file is editable Mermaid source.\n\n1. Upload and compatibility\n2. Row validation and model selection\n3. Results, explanations and exports\n\nRegenerate with `backend/.venv/Scripts/python.exe diagrams/build_diagrams.py` from the project root. Generated from the implemented 1.1.1 workflow in backend/import_analysis.py, backend/app.py and Design/src/App.tsx.\n',encoding='utf-8')
print('Created',len(items),'SVG diagrams, Mermaid sources, and offline index.html')
