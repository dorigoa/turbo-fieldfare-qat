#git clone git@github.com:dorigoa/turbo-fieldfare-fork.git
git clone git@github.com:drumih/turbo-fieldfare.git
python3 ./pin_model.py --repo-path ./turbo-fieldfare-fork/
cd turbo-fieldfare
mkdir -p Scratch
cp ../build-app.sh Scratch/
Scratch/build-app.sh --install
