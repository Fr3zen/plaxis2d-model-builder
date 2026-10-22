import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {Workbook,SpreadsheetFile,FileBlob} from '@oai/artifact-tool';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const c=JSON.parse(await fs.readFile(path.join(root,'examples/demo.json'),'utf8'));
const labels=JSON.parse(await fs.readFile(path.join(root,'pitbuilder/workbook_headers.json'),'utf8'));
const calcLabels={'Plastic':'塑性','Consolidation':'固结','Safety':'安全分析','Fully coupled flow-deformation':'完全耦合渗流—变形'};
const stageUpdate=process.argv.includes('--stage-update');
const interfaceUpdate=process.argv.includes('--interface-update');
const editMode=stageUpdate||interfaceUpdate;
const templatePath=path.join(root,'基坑建模模板.xlsx');
const wb=editMode?await SpreadsheetFile.importXlsx(await FileBlob.load(templatePath)):Workbook.create();
const specs=[];
specs.push(['使用说明',['项目','填写说明'],[
 ['用途','从空白工程建立地层、基坑、施工阶段和水条件；默认不计算。'],
 ['数据来源','所有示例均为软件验证用演示数据，不是现场或设计参数。'],
 ['单位','坐标/标高/绝对水头：m；时间/水力阻力：day；力：kN。'],
 ['填写顺序','工程 → 钻孔 → 材料与赋材 → 围护/支撑 → 初始水 → 施工阶段 → 水力方案/漏水段。'],
 ['固定格式','数据表第1行为字段名，请勿改表名和字段名；从第2行开始填写；数值不可用公式。'],
 ['材料 properties','按所选本构填写完整参数JSON；ERef为刚度，cref为有效黏聚力，phi为有效摩擦角；不同本构不能混用。'],
 ['工程 parameter','xmin/ymin/xmax/ymax 为模型外包范围；start_y为施工起始标高；四个Boundary字段明确Open或Closed。'],
 ['围护 walls','x/top/bottom 为墙坐标和顶底标高；material 为板材料ID；interface_material 为界面力学材料ID。'],
 ['施工 operation','walls围护；dewater降水；excavate开挖；support支撑；wait停歇；slab垫层。previous填前序ID，首个填INITIAL。'],
 ['阶段时间','仅填写阶段历时（天），不再输入速度。固结/完全耦合需大于0；塑性/安全允许0。结构安装阶段填structure_ids。'],
 ['计算类型','每阶段下拉选择：塑性、固结、安全分析、完全耦合渗流—变形。孔压方式默认自动；安全沿用前序，完全耦合使用耦合孔压。'],
 ['降水 mode','equivalent_head：水平等效定水头线；drain：实际正常排水线。points给坐标，head给绝对总水头，seepage启用当期暴露面排水。'],
 ['超前降水','不把仍保留的土体设为Dry。目标水头和排水设施位置分别填写，等效控制线不代表实际井。'],
 ['漏水 mode','resistance：有限透水，resistance_days为总墙段水力阻力；permeable：完全透水。first/last填启用起止阶段。'],
 ['局部水条件','初始水条件GLOBAL用于全局；其他region_id需提供polygon坐标JSON，区域不能重叠；每个区域按x递增填水位控制点。'],
 ['零厚度','同一孔相邻层底可相等，代表缺层/尖灭；不能留空或用任意0代替未知数据。'],
 ['结果检查','先双击检查与预览，再核对分期剖面和设置清单，最后生成新模型。程序不覆盖已有工程。']]]);
const p=c.project;
specs.push(['工程',['parameter','value'],[['name',p.name],...['xmin','ymin','xmax','ymax'].map((k,i)=>[k,p.bounds[i]]),['start_y',p.start_y],...Object.entries(p.flow_boundaries)]]);
specs.push(['钻孔数据',['钻孔编号','沿剖面距离 x（m）','孔口标高（m）',...c.geology.layers.map(l=>l.name+'层底标高（m）')],c.geology.boreholes.map(h=>[h.id,h.x,h.ground,...h.bottoms])]);
specs.push(['地层材料',['layer_id','material_id'],Object.entries(c.layer_materials)]);
for(const [key,title,headers] of [
 ['materials','材料',['id','kind','properties','dll_path','udsm_parameter_count']],
 ['walls','围护结构',['id','x','top','bottom','material','interface_material']],
 ['structures','支撑与垫层',['id','kind','y','material','prestress']],
 ['stages','施工阶段',['id','previous','operation','calculation_type','duration_days','excavation_y','structure_ids','hydraulic_plan','pore_pressure_type']],
 ['hydraulic_plans','水力方案',['id','mode','head','points','seepage']],
 ['leaks','漏水段',['id','wall','top','bottom','first','last','mode','resistance_days']]]) {
 specs.push([title,headers,c[key].map(o=>headers.map(h=>h==='calculation_type'?(calcLabels[o[h]]??o[h]??'固结'):h==='pore_pressure_type'?(o[h]??'自动'):o[h]===undefined?null:typeof o[h]==='object'?JSON.stringify(o[h],null,h==='properties'?2:0):o[h]))]);
}
specs.push(['初始水条件',['region_id','x_m','head_m','polygon'],p.initial_water.map(v=>['GLOBAL',...v,null])]);
await fs.mkdir(path.join(root,'verification','workbook'),{recursive:true});
if(interfaceUpdate){
 const wall=wb.worksheets.getItem('围护结构'),materials=wb.worksheets.getItem('材料');
 for(const sh of [wall,materials]){
   const before=await wb.render({sheetName:sh.name,range:sh.getUsedRange().address,scale:1,format:'png'});
   await fs.writeFile(path.join(root,'verification','workbook',sh.name+'_before_interfaces.png'),new Uint8Array(await before.arrayBuffer()));
 }
 const rows=wall.getUsedRange().values;
 const col=rows[0].findIndex(v=>['界面材料编号','界面赋材（AUTO=按土层）','interface_material'].includes(v));
 if(col<0)throw Error('围护结构缺少界面赋材列');
 wall.getRangeByIndexes(0,col,1,1).values=[['界面赋材（AUTO=按土层）']];
 for(let i=1;i<rows.length;i++)if(rows[i][0])wall.getRangeByIndexes(i,col,1,1).values=[['AUTO']];
 const mr=materials.getUsedRange().values;
 for(let i=1;i<mr.length;i++)if(mr[i][0]==='gong'&&mr[i][1]==='beam'){
   const props=JSON.parse(mr[i][2]);
   if(process.argv.includes('--gong-axial')){
     if(!('EA' in props&&'LSpacing' in props))throw Error('gong缺少轴向支撑参数');
     materials.getRangeByIndexes(i,1,1,1).values=[['anchor']];
   }else{
     if(!('EA1' in props&&'EI' in props))throw Error('gong不是可确认的板材料，停止自动归类');
     materials.getRangeByIndexes(i,1,1,1).values=[['plate']];
   }
 }
 if(process.argv.includes('--gong-axial')){
   const structures=wb.worksheets.getItem('支撑与垫层'),sr=structures.getUsedRange().values;
   for(let i=1;i<sr.length;i++)if(sr[i][0]==='S1'&&sr[i][3]==='gong')structures.getRangeByIndexes(i,1,1,1).values=[['anchor']];
 }
 const soilIds=mr.slice(1).filter(r=>r[1]==='soil').map(r=>r[0]);
 wall.getRangeByIndexes(1,col,499,1).dataValidation={rule:{type:'list',values:['AUTO',...soilIds]}};
 wall.getRangeByIndexes(0,col,rows.length,1).format.columnWidth=34;
 wall.getRangeByIndexes(0,col,1,1).format.wrapText=true;
 const guide=wb.worksheets.getItem('使用说明'),guideRows=guide.getUsedRange().values;
 for(let i=0;i<guideRows.length;i++)if(String(guideRows[i][0]).startsWith('围护')){
   guide.getRangeByIndexes(i,1,1,1).values=[['界面赋材填AUTO：按墙与各土层实际交点切分，各段复制相邻土层的界面力学参数；阻水/漏水另行设置。明确填土体材料ID时为整墙自定义覆盖。']];
   guide.getRangeByIndexes(i,0,1,2).format.rowHeight=65;
 }
 wb.recalculate();
 for(const sh of [wall,materials,guide,...(process.argv.includes('--gong-axial')?[wb.worksheets.getItem('支撑与垫层')]:[])]){
   const after=await wb.render({sheetName:sh.name,range:sh.getUsedRange().address,scale:1,format:'png'});
   await fs.writeFile(path.join(root,'verification','workbook',sh.name+'.png'),new Uint8Array(await after.arrayBuffer()));
 }
 if(!stageUpdate)specs.length=0;
}
if(stageUpdate){
 if(process.argv.includes('--confirmed-borehole-fix')){
   const boreholes=wb.worksheets.getItem('钻孔数据');
   boreholes.getRange('B2:B5').values=[[-40],[-20],[20],[40]];
 }
 if(process.argv.includes('--fourth-layer-placeholder')){
   const boreholes=wb.worksheets.getItem('钻孔数据');
   boreholes.getRange('G1').values=[['第四层层底标高（m）']];
   boreholes.getRange('G1:G5').format.columnWidth=25;
   boreholes.getRange('G1:G5').format.font={name:'Microsoft YaHei',size:10};
   boreholes.getRange('G1').format.fill='#243F53';
   boreholes.getRange('G1').format.font={name:'Microsoft YaHei',size:10,bold:true,color:'#FFFFFF'};
   boreholes.getRange('G1').format.wrapText=true;
 }
 const sh=wb.worksheets.getItem('施工阶段');
 const before=sh.getUsedRange().values;
 const aliases=Object.fromEntries(Object.entries(labels['施工阶段']).map(([k,v])=>[v,k]));
 aliases['等效开挖速度（m/天）']='speed_m_day';
 const oldHeaders=before[0].map(h=>aliases[h]??h),levels={INITIAL:c.project.start_y};
 const rows=before.slice(1).filter(r=>r.some(v=>v!==null&&v!=='')).map(r=>Object.fromEntries(oldHeaders.map((h,i)=>[h,r[i]])));
 for(const row of rows){
   const previous=levels[row.previous];
   if((row.duration_days===null||row.duration_days===undefined||row.duration_days==='')&&row.speed_m_day){
     if(row.operation!=='excavate'||!Number.isFinite(previous)||!(row.speed_m_day>0))throw Error('旧速度行无法迁移，请明确阶段历时：'+row.id);
     row.duration_days=(previous-row.excavation_y)/row.speed_m_day;
   }
   levels[row.id]=row.operation==='excavate'?row.excavation_y:previous;
   row.calculation_type=calcLabels[row.calculation_type]??row.calculation_type??'固结';row.pore_pressure_type=row.pore_pressure_type||'自动';
 }
 specs.length=0;
 specs.push(['施工阶段',['id','previous','operation','calculation_type','duration_days','excavation_y','structure_ids','hydraulic_plan','pore_pressure_type'],rows.map(o=>['id','previous','operation','calculation_type','duration_days','excavation_y','structure_ids','hydraulic_plan','pore_pressure_type'].map(k=>o[k]??null))]);
 sh.getUsedRange().clear({applyTo:'all'});
 const guide=wb.worksheets.getItem('使用说明'),guideRows=guide.getUsedRange().values;
 for(let i=0;i<guideRows.length;i++)if(guideRows[i][0]==='阶段时间')guide.getRangeByIndexes(i,1,1,1).values=[['仅填写阶段历时（天），不再输入速度。固结/完全耦合需大于0；塑性/安全允许0。计算类型见施工阶段下拉；孔压可选自动。']];
 const blob=await wb.render({sheetName:'使用说明',range:guide.getUsedRange().address,scale:1,format:'png'});
 await fs.writeFile(path.join(root,'verification','workbook','使用说明.png'),new Uint8Array(await blob.arrayBuffer()));
 if(process.argv.includes('--confirmed-borehole-fix')||process.argv.includes('--fourth-layer-placeholder')){
   const boreholes=wb.worksheets.getItem('钻孔数据');
   const geoBlob=await wb.render({sheetName:'钻孔数据',range:boreholes.getUsedRange().address,scale:1,format:'png'});
   await fs.writeFile(path.join(root,'verification','workbook','钻孔数据.png'),new Uint8Array(await geoBlob.arrayBuffer()));
 }
}
for(const [name,headers,rows] of specs){
 const sh=editMode?wb.worksheets.getItem(name):wb.worksheets.add(name);const n=rows.length+1,m=headers.length;
 const displayHeaders=headers.map(h=>labels[name]?.[h]??h);
 sh.getRangeByIndexes(0,0,n,m).values=[displayHeaders,...rows];
 sh.getRangeByIndexes(0,0,n,m).format.font={name:'Microsoft YaHei',size:10};
 sh.getRangeByIndexes(0,0,n,m).format.columnWidth=19;
 sh.getRangeByIndexes(0,0,n,m).format.rowHeight=28;
 sh.getRangeByIndexes(0,0,1,m).format.fill='#243F53';
 sh.getRangeByIndexes(0,0,1,m).format.font={name:'Microsoft YaHei',size:10,bold:true,color:'#FFFFFF'};
 sh.getRangeByIndexes(0,0,1,m).format.wrapText=true;
 sh.getRangeByIndexes(0,0,1,m).format.rowHeight=46;
 sh.getRangeByIndexes(1,0,n-1,m).format.font={name:'Microsoft YaHei',size:10,color:'#155B8A'};
 sh.getRangeByIndexes(1,0,n-1,m).format.numberFormat='0.########';
 if(name==='使用说明'){
   sh.getRange('A1:A17').format.columnWidth=22;sh.getRange('B1:B17').format.columnWidth=100;
   sh.getRange('B2:B17').format.wrapText=true;sh.getRange('A2:B17').format.rowHeight=44;
 } else sh.freezePanes.freezeRows(1);
 if(name==='材料'){
   sh.getRange('C1:C4').format.columnWidth=65;sh.getRange('C2:C4').format.wrapText=true;
   sh.getRange('A2:C4').format.rowHeight=185;
 }
 if(name==='工程')sh.getRange('B1:B11').format.columnWidth=48;
 if(name==='钻孔数据')sh.getRangeByIndexes(0,0,n,m).format.columnWidth=25;
 if(name==='水力方案')sh.getRange('D1:D2').format.columnWidth=36;
 if(name==='施工阶段'){
   sh.getRange('D1:D500').format.columnWidth=32;sh.getRange('I1:I500').format.columnWidth=32;
   sh.getRange('D2:D500').dataValidation={rule:{type:'list',values:['塑性','固结','安全分析','完全耦合渗流—变形']}};
   sh.getRange('I2:I500').dataValidation={rule:{type:'list',values:['自动','潜水位生成','沿用前序孔压','稳态地下水流','完全耦合渗流—变形']}};
 }
 const blob=await wb.render({sheetName:name,range:sh.getRangeByIndexes(0,0,Math.min(n,17),m).address,scale:1,format:'png'});
 await fs.writeFile(path.join(root,'verification','workbook',name+'.png'),new Uint8Array(await blob.arrayBuffer()));
}
wb.recalculate();
const check=await wb.inspect({kind:'region',sheetId:'施工阶段',range:'A1:I6',maxChars:1800});
await fs.writeFile(path.join(root,'verification','workbook','inspect.txt'),check.ndjson);
await (await SpreadsheetFile.exportXlsx(wb)).save(path.join(root,'基坑建模模板.xlsx'));
console.log(editMode?'Updated requested input sheets in place; preserved other sheets.':'Exported 11 sheets including instructions; rendered each populated sheet.');
