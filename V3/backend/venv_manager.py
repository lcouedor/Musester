import os
import subprocess

def activate():
    if 'VIRTUAL_ENV' in os.environ:
        print('Already in a virtual environment')
        return
    if not os.path.exists('myenv/bin/activate'):
        print('No virtual environment found')
        return
    print('Activating virtual environment...')
    os.system('bash -c "source myenv/bin/activate && exec bash"')
    print('Virtual environment activated')

def deactivate():
    if 'VIRTUAL_ENV' not in os.environ:
        print('Not in a virtual environment')
        return
    print('Deactivating virtual environment...')
    subprocess.call(['exit', 'deactivate'], shell=True)
    print('Virtual environment deactivated')

def create():
    print('Creating virtual environment...')
    subprocess.call(['python3', '-m', 'venv', 'myenv'])
    print('Virtual environment created')

def remove():
    if os.path.exists('myenv'):
        print('Removing virtual environment...')
        os.system('rm -rf myenv')
        print('Virtual environment removed')
    else:
        print('No virtual environment found')

def install_requirements():
    print('Installing dependencies from requirements.txt...')
    subprocess.call(['pip', 'install', '-r', 'requirements.txt'])

def see_installed_packages():
    print('Installed packages:')
    subprocess.call(['pip', 'freeze'])

def main():
    print('1. Create virtual environment')
    print('2. Activate virtual environment')
    print('3. Deactivate virtual environment')
    print('4. Remove virtual environment')
    print('5. Install dependencies')
    print('6. See installed packages')
    
    choice = input('Enter your choice: ')
    if choice == '1':
        create()
    elif choice == '2':
        activate()
    elif choice == '3':
        deactivate()
    elif choice == '4':
        remove()
    elif choice == '5':
        install_requirements()
    elif choice == '6':
        see_installed_packages()
    else:
        print('Invalid choice')

if __name__ == '__main__':
    main()



# python3 -m venv venv
# pip install -r requirements.txt
# python main.py