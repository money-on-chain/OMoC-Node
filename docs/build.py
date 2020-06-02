import shutil   
import markdown2
import os,re

template = "resources/template.html"
files = ["index","step02", "step03", "step04"]
build = "./build"
resources = "./resources"
mdFolder = "./markdown"
if os.path.exists(build):
	shutil.rmtree(build) 
file = open(template,mode='r')
templateContent = file.read()
file.close()
destination = shutil.copytree(resources, build)
for file in files:
	htmlFile = build + "/" + file + ".html" 
	mdFile = mdFolder + "/" + file + ".md"

	if os.path.exists(build + "/" + file): os.remove(htmlFile) 
	#generate html from mmdFile and return body content from HTML
	print (mdFile)
	body = markdown2.markdown_path(mdFile)
	body = re.sub(r'<img',r'<img class="img-fluid"',body)
	if file=="index":
		templateIndex = re.sub(r'<a href="index.*</a>',r'',templateContent,re.DOTALL) if file=="index" else body
		html = re.sub("ID_CONTENIDO",body,templateIndex)
	else:
		html = re.sub("ID_CONTENIDO",body,templateContent)

	file = open(htmlFile,"w+") 
	file.write(html)
	file.close()