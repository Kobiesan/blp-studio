"""Per-user preferences; no machine-specific paths are bundled with the app."""
import json,os
from pathlib import Path

def settings_path():
    base=Path(os.environ.get('APPDATA') or (Path.home()/'.config'))
    return base/'BLP Studio/settings.json'

class Preferences:
    def __init__(self,path=None):
        self.path=Path(path) if path else settings_path()
        try:self.data=json.loads(self.path.read_text(encoding='utf-8'))
        except (OSError,ValueError):self.data={}
        if not isinstance(self.data,dict):self.data={}
    def folder(self):
        value=self.data.get('last_folder','')
        return value if isinstance(value,str) and Path(value).is_dir() else ''
    def remember(self,file):
        self.data['last_folder']=str(Path(file).resolve().parent);self.save()
    def save(self):
        try:
            self.path.parent.mkdir(parents=True,exist_ok=True)
            temp=self.path.with_suffix('.tmp');temp.write_text(json.dumps(self.data,indent=2),encoding='utf-8');temp.replace(self.path)
        except OSError:pass # Read-only preference storage must not break conversion.
