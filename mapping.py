# generates ASTRID-multi mapping files from multicopy gene trees
import treeswift as ts
from treeswift import Tree, Node
from collections import deque, defaultdict
from random import choice
from itertools import groupby
from random import sample
import os, sys
fn = sys.argv[1]
labels = set()
with open(fn) as fh:
    for l in fh:
        tre = ts.read_tree_newick(l)
        labels.update(tre.labels(True, False))
speciesd = defaultdict(set)
for l in labels:
    s = l.split("_")[0]
    speciesd[s].add(l)
with open(f"{fn}.map", "w+") as oh:
    for k in speciesd:
        vocab = " ".join(speciesd[k])
        oh.write(f"{k} {vocab}\n") 
