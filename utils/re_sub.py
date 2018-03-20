import re

file_name = "templates/index.html"  # 修改文件
with open(file_name, "r") as f:
    content = f.read()

def change_content(sub_str):
    sub_str = sub_str.group("url")
    return "src='{% static " + '"' + str(sub_str) + '"' +" %}'"

# 替换静态模板
content = re.sub(r'src="(?P<url>[^\{].*?)"', change_content, content)
# content = re.findall(r'src="(?P<url>[^\{].*?)"', content)
# print(content)

with open(file_name + '_sub', 'w') as f:
    f.write(content)