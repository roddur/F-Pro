
"""
@author: Payam Dibaeinia
"""

import numpy as np
import shutil
from Sampler import gtSampler
import time
import pandas as pd
import os
import subprocess

def file_len(fname):
    p = subprocess.Popen(['wc', '-l', fname], stdout=subprocess.PIPE, 
                                              stderr=subprocess.PIPE)
    result, err = p.communicate()
    if p.returncode != 0:
        raise IOError(err)
    return int(result.strip().split()[0])


class FASTRAL (object):

    def __init__(self, flags):

        nt = [int(i) for i in flags.nt.split(',')]
        ns = [int(i) for i in flags.ns.split(',')]
        self.prefix_f = os.path.abspath(os.path.dirname(__file__))
        print(self.prefix_f)

        self.flags_ = flags
        if flags.incomp_id != None:
            incomp_id = pd.read_csv(flags.incomp_id, header = None, index_col = None)
            incomp_id = incomp_id.values.flatten()
        else:
            incomp_id = None
        
        if flags.decomp:
            os.system("python "+self.prefix_f+"/tag_decomp.py -i "+ flags.it)
            split = flags.it.rsplit('.', 1)
            flags_it = split[0] + '-decomp.' + split[1]
            os.system("python "+self.prefix_f+"/relabel_and_strip_multrees_simphy.py -i "+ flags_it)

            base = flags_it.rsplit('.',1)
            flags_it = base[0] + "-mult." + base[1]
            self.new_f = file_len(flags.it)-1
            ratio = self.new_f/flags.k
            #print("vuchku",self.new_f,ratio)
            nt = [int(i * ratio) for i in nt]


        print("START BUILDING SAMPLES ... ", flush=True)
        sampler = gtSampler(nTree = nt, nSample = ns, k = self.new_f, replacement = flags.rep, missingID = incomp_id)
        sampler.create_samples(path_read = flags_it, path_write = flags.os)

        self.path_samples = self.flags_.os + '/Sample_'
        self.nTotalS_ = np.sum(ns)

        self.multi = self.flags_.multi

    def run(self):
        t1 = time.time()
        self._run_ASTRID()
        t2 = time.time()

        self._aggregate_ASTRID_trees()

        t3 = time.time()
        self._run_ASTRAL()
        t4 = time.time()

        """
        write running times
        """
        header = ['ASTRID_time', 'ASTRAL_time', 'total_time']
        df = pd.DataFrame([[t2-t1, t4-t3, t2-t1 + t4-t3]])
        df.to_csv(self.flags_.time, header = header, sep = '\t', index = False)


    def _run_ASTRID(self):

        print("START RUNNING ASTRID ... ", flush=True)
        cline = self.flags_.path_ASTRID + ' -i ' + self.path_samples

        for s in range(self.nTotalS_):
            curr_cline = cline + str(s) + '/sampledGeneTrees'
            if self.multi and not self.flags_.decomp:
                mymulti = self.path_samples+ str(s) + '/sampledGeneTrees'
                os.system("python "+self.prefix_f+"/mapping.py "+mymulti)
                curr_cline += ' -a '+mymulti+'.map' + ' -o ' + self.path_samples + str(s) + '/ASTRID_species_tree_' + str(s)
            else:
                curr_cline += ' -o ' + self.path_samples + str(s) + '/ASTRID_species_tree_' + str(s)

            print("     Running ASTRID on sample " + str(s) + " : " + curr_cline, flush=True)
            status = os.system(curr_cline)
            if status < 0:
                raise ValueError('ASTRID was not run successfully')

    def _aggregate_ASTRID_trees(self):

        print("START AGGREGATING ASTRID's OUTPUTS ... ", flush=True)

        with open(self.flags_.aggregate,'wb') as wf:
            for s in range(self.nTotalS_):
                path = self.path_samples + str(s) +'/ASTRID_species_tree_' + str(s)
                with open(path,'rb') as rf:
                    shutil.copyfileobj(rf, wf)

    def _run_ASTRAL(self):

        if self.multi:
            os.system("python "+self.prefix_f+"/relabel_and_strip_multrees_simphy.py -i "+ self.flags_.it)

            base = self.flags_.it.rsplit('.',1)
            self.flags_.it = base[0] + "-mult." + base[1]

            cline = self.flags_.path_ASTRAL + ' -c ' + self.flags_.aggregate + ' -o ' + self.flags_.o + " " + self.flags_.it
        else:
            cline = self.flags_.path_ASTRAL + ' -c ' + self.flags_.aggregate + ' -o ' + self.flags_.o + " " + self.flags_.it
        print("START RUNNING ASTRAL ... ", flush=True)
        print(cline)
        status = os.system(cline)
        if status < 0:
            raise ValueError('ASTRAL was not run successfully')
