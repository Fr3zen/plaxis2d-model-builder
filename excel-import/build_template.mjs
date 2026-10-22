import fs from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { Workbook, SpreadsheetFile } from '@oai/artifact-tool';
const dir = new URL('.', import.meta.url);
const wb = Workbook.create();
const sh = wb.worksheets.add('钻孔数据');
sh.showGridLines = false;
sh.getRange('A1:F4').values = [
  ['钻孔编号','沿剖面距离 x（m）','孔口标高（m）','填土层底标高（m）','黏土层底标高（m）','砂土层底标高（m）'],
  ['ZK1',0,10,8,1,-15],
  ['ZK2',30,12,9,-2,-15],
  ['ZK3',70,9,6,0,-15],
];
sh.getRange('A1:F4').format.font = {name:'Arial',size:11,color:'#243746'};
sh.getRange('A1:F1').format = {fill:'#24465C',font:{name:'Arial',size:11,bold:true,color:'#FFFFFF'},rowHeight:34,horizontalAlignment:'center',verticalAlignment:'center'};
sh.getRange('A1:A4').format.columnWidth = 16;
sh.getRange('B1:F4').format.columnWidth = 25;
sh.getRange('A2:F4').format.rowHeight = 28;
sh.getRange('B2:F4').setNumberFormat('0.00');
sh.getRange('B2:F4').format.fill = '#FFF4DB';
sh.getRange('H1').values=[['填写说明']];
sh.getRange('H1:H7').format.columnWidth=76;
sh.getRange('H1:H7').format.font={name:'Arial',size:11,color:'#526575'};
sh.getRange('H2:H7').values=[
  ['演示数据。长度及标高单位均为 m。'],
  ['第一行保留列名，第二行起一行一个钻孔。'],
  ['层底填写统一基准的标高，不是孔口以下埋深。'],
  ['各层从浅到深排列；可以新增钻孔行和层底标高列。'],
  ['缺层、尖灭及零厚度不自动解释；请先明确地层连接。'],
  ['仅导入地层几何。材料、水条件和施工阶段需另行设置。'],
];
wb.recalculate();
console.log((await wb.inspect({kind:'table',range:'钻孔数据!A1:F4',include:'values',tableMaxRows:4,tableMaxCols:6,maxChars:2500})).ndjson);
const preview = await wb.render({sheetName:'钻孔数据',range:'A1:H7',scale:1,format:'png'});
await fs.writeFile(new URL('template_preview.png',dir),new Uint8Array(await preview.arrayBuffer()));
await (await SpreadsheetFile.exportXlsx(wb)).save(fileURLToPath(new URL('钻孔数据模板.xlsx',dir)));
