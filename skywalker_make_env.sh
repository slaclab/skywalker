echo "enter git username: "                                                     
read USERNAME                                                                   
                                                                                
echo "echo conda env name: "                                                    
read ENVNAME                                                                    
                                                                                
conda create -n $ENVNAME pip wheel pytest coverage ophyd bluesky -c conda-forge -c lightsource2-tag
source activate $ENVNAME                                                        
                                                                                
packages=("happi" "lightpath" "pswalker" "pcds-devices" "psbeam")               
                                                                                
for i in "${packages[@]}"                                                       
do                                                                              
    git clone "https://$USERNAME@github.com/$USERNAME/$i.git";                  
    cd $i                                                                       
    git remote add upstream "https://github.com/slaclab/$i.git"                 
    pip install -r requirements.txt                                             
    python setup.py develop                                                     
    cd ..                                                                       
done  