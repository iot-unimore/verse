# First Setup
After cloning the repo you have to make sure your environment is setup correclty.

There are three things to take care of:
- your python setup
- binary tools
- resource files

## Python setup
To quickly setup python dependencies it is suggested to use [Conda] (https://docs.conda.io/projects/conda/en/stable/user-guide/getting-started.html).
This is to keep an isolated environment dedicated to the dataset toolchain.

After installing Conda open a shell and create your "verse" environment:
```
conda create -n "verse" python=3.10.0
```
Activate your new environment with
```
conda activate verse
```
Enter the VERSE repository and use the "requirements.txt" file to update your environment:
```
pip install -r requirements.txt
```

Remeber to activate your "verse" python environment each time you want to use the toolchain or render new audio data.

## Fetching external files

## Compile tools

