"""Retain original package, transplant only Word-refreshed body and TOC."""
from copy import deepcopy
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from io import BytesIO
from lxml import etree

root=Path(__file__).resolve().parents[1]
target=root/'artifacts/ДЗ1_Кузин_Тимур.docx'
baseline=root/'artifacts/qa/report-before-fields.docx'
W='http://schemas.openxmlformats.org/wordprocessingml/2006/main'
R='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
ns={'w':W}
with ZipFile(baseline) as a, ZipFile(target) as b:
    xml=etree.fromstring(b.read('word/document.xml'))
    before_rels=etree.fromstring(a.read('word/_rels/document.xml.rels'))
    after_rels=etree.fromstring(b.read('word/_rels/document.xml.rels'))
    old_targets={(r.get('Type'),r.get('Target')):r.get('Id') for r in before_rels}
    mapping={r.get('Id'):old_targets.get((r.get('Type'),r.get('Target'))) for r in after_rels}
    for node in xml.iter():
        for key,value in list(node.attrib.items()):
            if key.startswith('{'+R+'}'):
                assert mapping.get(value), ('unmapped relationship',value)
                node.set(key,mapping[value])
    oldstyles=etree.fromstring(a.read('word/styles.xml'))
    newstyles=etree.fromstring(b.read('word/styles.xml'))
    old_names={s.find('w:name',ns).get('{'+W+'}val'):s.get('{'+W+'}styleId') for s in oldstyles.findall('w:style',ns)}
    new_ids={s.get('{'+W+'}styleId'):s.find('w:name',ns).get('{'+W+'}val') for s in newstyles.findall('w:style',ns)}
    added=[]
    for node in xml.xpath('//w:pStyle | //w:rStyle | //w:tblStyle',namespaces=ns):
        value=node.get('{'+W+'}val'); name=new_ids[value]
        if name not in old_names:
            # Word may materialize TOC styles; allow only those new styles.
            assert name.lower().startswith('toc') or name.lower() == 'hyperlink',name
            s=deepcopy(next(s for s in newstyles.findall('w:style',ns) if s.get('{'+W+'}styleId')==value))
            oldstyles.append(s); old_names[name]=value; added.append(name)
        node.set('{'+W+'}val',old_names[name])
    oldbody=etree.fromstring(a.read('word/document.xml'))
    newsect=xml.find('w:body/w:sectPr',ns)
    newsect.getparent().replace(newsect,deepcopy(oldbody.find('w:body/w:sectPr',ns)))
    payload=etree.tostring(xml,xml_declaration=True,encoding='UTF-8',standalone=True)
    result=BytesIO()
    with ZipFile(result,'w',ZIP_DEFLATED) as out:
        for info in a.infolist():
            data=payload if info.filename=='word/document.xml' else a.read(info.filename)
            if info.filename=='word/styles.xml' and added:
                data=etree.tostring(oldstyles,xml_declaration=True,encoding='UTF-8',standalone=True)
            out.writestr(info,data)
    target.write_bytes(result.getvalue())
    print('Preserved baseline package; refreshed body and TOC. Added TOC styles:',added)
