"""Package a portable executable with documentation, licenses and SHA256."""
import hashlib,sys,zipfile
from pathlib import Path

def package(executable):
    root=Path(__file__).resolve().parent;executable=Path(executable).resolve()
    if not executable.is_file():raise FileNotFoundError(executable)
    version=(root/'VERSION').read_text().strip();output=root/'dist';output.mkdir(exist_ok=True)
    archive=output/f'BLP-Studio-{version}-windows-x64.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as zip:
        zip.write(executable,'BLPStudio.exe')
        for name in ('README.md','LICENSE','THIRD_PARTY_NOTICES.md','ASSETS.md','CHANGELOG.md','VERSION'):
            zip.write(root/name,name)
        for file in sorted((root/'licenses').glob('*')):
            if file.is_file():zip.write(file,'licenses/'+file.name)
    checksum=archive.with_suffix('.zip.sha256')
    checksum.write_text(hashlib.sha256(archive.read_bytes()).hexdigest()+'  '+archive.name+'\n')
    print(archive.name);print(checksum.name)

if __name__=='__main__':package(sys.argv[1] if len(sys.argv)>1 else 'dist/BLPStudio.exe')
