# Rebuilds "multimedia" entries of the brain,
# leaving intact "text" entries

import json
from pathlib import Path
from ast import literal_eval


ai_brain_file = "ai_brain.json"
ai_brain = {}
ai_media_root_path = ".\\ai_media"


def save_ai():
	with open(ai_brain_file, 'w') as f:
		json.dump(ai_brain, f, indent=2)


def load_ai():
	global ai_brain
	with open(ai_brain_file) as f:
		ai_brain=json.load(f)


def add_brain_string(verb, subj, author, mediapath):
	global ai_brain

	if verb not in ai_brain: ai_brain[verb] = {}
	if subj not in ai_brain[verb]: ai_brain[verb][subj] = []
	content = literal_eval('{"author": ' + json.dumps(author) + ',"content": ' + json.dumps(mediapath) + '}')
	if not content in ai_brain[verb][subj]:
		ai_brain[verb][subj].append(content)


# Main
load_ai()
print("AI loaded")
print("Scanning media in {dir}".format(dir=Path(ai_media_root_path).absolute()))
for file in Path(ai_media_root_path).glob('**/*.*'):
	print("    found: {name}".format(name=file))
	if file.stem.find('_') > 0 :
		author = file.stem.split('_')[0]
	else:
		author = 'Make Brain'
	add_brain_string(file.parts[1], file.parts[2], author, "[Multimedia|Type:|Caption:|Name:.\{nm}]".format(nm=file))
print("Media scan finished")
save_ai()
print("AI saved")
print("Available brain commands:")
for verb in ai_brain:
	for subj in ai_brain[verb]:
		print("{vrb} {sbj} [{num}]".format(vrb=verb, sbj=subj, num=len(ai_brain[verb][subj])))

