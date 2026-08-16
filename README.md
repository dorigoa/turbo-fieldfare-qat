# Purpose
Use QAT version of the original model and produce and install bundle app in /Applications

# Instructions
```
git clone git@github.com:dorigoa/turbo-fieldfare-qat.git
cd turbo-fieldfare-qat
./makeall.sh
```

`makeall.sh` script clones locally [turbo-fieldfare-fork](https://github.com/dorigoa/turbo-fieldfare-fork) and applies patches to it.

The purpose of the (3) patches applied (actually by the `pin_model.py` script called by `makeall.sh`) is to download and use the QAT version of gemma-4-26b-a4b-it (q4) instead of the normal one. QAT (quantised aware training) is supposed to be a little more precise than the quantized one.

Finally the called script `build_app.sh` launch the build and create the bundle .app in /Applications.
