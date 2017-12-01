import versioneer
from setuptools import setup, find_packages

setup(name='skywalker',
      version=versioneer.get_version(),
      cmdclass=versioneer.get_cmdclass(),
      license='BSD',
      author='SLAC National Accelerator Laboratory',
      packages=find_packages(),
      include_package_data=True,
      description='Automated beam alignment for LCLS',
      scripts=['scripts/lightpath', 'scripts/skywalker']
      )
