from setuptools import setup, find_packages

setup(
    name="openenergy",
    version="0.1.0",
    description="OpenEnergy: Energy market simulation and optimization platform",
    author="Akhilesh Koul",
    author_email="koulakhilesh@gmail.com",
    packages=find_packages(where="scripts"),
    package_dir={"": "scripts"},
    include_package_data=True,
    install_requires=[],  # You can add dependencies here or parse from requirements.txt
    python_requires=">=3.8",
)
