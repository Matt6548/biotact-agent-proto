# prepare_docs.py — делает *.docx.txt из всех .docx в папке (без доп. библиотек)
import zipfile, re, html, glob, os

def extract_docx_to_txt(path):
    with zipfile.ZipFile(path) as z:
        xml = z.read('word/document.xml').decode('utf-8', errors='ignore')
    # заменяем параграфы на перенос строки и убираем теги
    text = re.sub(r'<w:p[^>]*>', '\n', xml)
    text = re.sub(r'<[^>]+>', '', text)
    text = html.unescape(text)
    # чистим пустые строки
    text = '\n'.join(line.strip() for line in text.splitlines() if line.strip())
    out = path + '.txt'
    with open(out, 'w', encoding='utf-8') as f:
        f.write(text)
    print(f'OK: {os.path.basename(out)}')

# пробегаем по всем DOCX в текущей папке
files = glob.glob('*.docx')
if not files:
    print('В папке нет .docx. Помести сюда 4 документа и запусти снова.')
else:
    for f in files:
        extract_docx_to_txt(f)
    print('Готово. Все .docx.txt созданы.')
