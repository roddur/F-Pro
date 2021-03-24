import treeswift
import argparse
import random
import copy
import sys


def unroot(tree):
    """
    Unroots treeswift tree. Adapted from treeswift 'deroot' function.
    This one doesn't contract (A,B); to A;

    Parameters
    ----------
    tree: treeswift tree

    Returns unrooted treeswift tree
    """
    if tree.root == None:
        return tree
    if tree.root.num_children() == 2:
        [left, right] = tree.root.child_nodes()
        if not right.is_leaf():
            right.contract()
        elif not left.is_leaf():
            left.contract()
    tree.is_rooted = False
    return tree


def remove_in_paralogs(tree, delimiter=None):
    """
    Removes in-paralogs from unrooted tree.

    Parameters
    ----------
    tree: treeswift tree
    delimiter: delimiter separating species name from rest of leaf label

    Returns number of in-paralogs removed
    """
    # root tree if not rooted
    if tree.root.num_children() != 2:
        tree.reroot(tree.root)

    num_paralogs = 0
    for node in tree.traverse_postorder():
        if node.is_leaf():
            node.s = set([node.get_label().split(delimiter)[0]])
        else:
            node.s = set([])
            for child in node.child_nodes():
                node.s = node.s.union(child.s)
            # collapse if paralogs
            if len(node.s) == 1:
                for child in node.child_nodes()[1:]:
                    node.remove_child(child)
                    num_paralogs += 1

    # check over top of root
    if any(len(child.s) == 1 for child in tree.root.child_nodes()):
        for node in tree.traverse_preorder():
            if not node.is_root():
                parent = node.get_parent()
                node.up = set([]) if parent.is_root() else parent.up
                for sibl in parent.child_nodes():
                    if sibl != node:
                        node.up.union(sibl.s)
                if len(node.up) == 1:
                    for sibl in parent.child_nodes():
                        if sibl != node:
                            parent.remove_child(sibl)
                            num_paralogs += 1
    tree.suppress_unifurcations()
    return num_paralogs


def get_min_root(tree, delimiter=None, verbose=False):
    """
    Calculates the root with the minimum score.

    Parameters
    ----------
    tree: treeswift tree
    delimiter: delimiter separating species name from rest of leaf label

    Returns vertex corresponding to best edge to root tree on
    """

    def score(total_set, set1, set2):
        if not len(set1.intersection(set2)) == 0:
                if total_set == set1 or total_set == set2:
                    if set1 == set2:
                        return 1
                    else:
                        return 2
                else:
                    return 3 
        return 0

    # check if tree is single leaf
    if tree.root.num_children() == 0:
        tree.root.s = set([tree.root.get_label()])
        return tree.root, 0, [] 

    # root tree if not rooted
    if tree.root.num_children() != 2:
        tree.reroot(tree.root)
    tree.resolve_polytomies()

    # Get down scores pass
    for node in tree.traverse_postorder():
        if node.is_leaf():
            node.down = set([node.get_label().split(delimiter)[0]])
            node.d_score = 0
        else:
            if node.num_children() != 2:
                raise Exception("Vertex has more than 2 children")

            [left, right] = node.child_nodes()
            node.down = left.down.union(right.down)
            node.d_score = left.d_score + right.d_score + score(node.down, left.down, right.down)

    min_score, best_root, ties = float("inf"), None, []

    # Get scores above edge pass
    for node in tree.traverse_preorder():
        if node.is_root():
            root = node
            root.skip = True
        else:
            node.skip = False

    # Get 'up' set for children of root
    [left, right] = root.child_nodes()
    left.up = right.down
    left.u_score = right.d_score
    right.up = left.down
    right.u_score = left.d_score
    left.skip = True
    right.skip = True

    min_score = left.u_score + left.d_score + score(left.up.union(left.down), left.up, left.down)
    # we don't want to root at a leaf
    if not left.is_leaf():
        best_root = left 
    elif not right.is_leaf():
        best_root = right
    # if both are leaves (i.e. two leaf tree), we want to keep the same rooting
    else:
        best_root = root
    ties = [best_root]

    for node in tree.traverse_preorder(leaves=False):
        if not node.skip:
            
            parent = node.get_parent()
            if parent.child_nodes()[0] != node:
                other = parent.child_nodes()[0]
            else: 
                other = parent.child_nodes()[1]

            node.up = parent.up.union(other.down)
            node.u_score = parent.u_score + other.d_score + score(node.up, parent.up, other.down)

            total_score = node.u_score + node.d_score + score(node.up.union(node.down), node.up, node.down)

            if total_score == min_score:
                ties.append(node)
                
            if total_score < min_score:
                num_ties = 0
                min_score = total_score
                best_root = node
                ties = [node]

    if verbose:            
        print('Best root had score', min_score, 'there were', len(ties), 'ties.')
        
    return best_root, min_score, ties


def tag(tree, delimiter=None):
    """
    Tags tree according to its current rooting.

    Parameters
    ----------
    tree: treeswift tree
    delimiter: delimiter separating species name from rest of leaf label
    """
    tree.suppress_unifurcations()
    tree.resolve_polytomies()
    for node in tree.traverse_postorder():
        if node.is_leaf():
            node.s = set([node.get_label().split(delimiter)[0]])
            node.n_dup = 0
        else:
            [left, right] = node.child_nodes()

            node.s = left.s.union(right.s)
            node.n_dup = left.n_dup + right.n_dup
            if len(left.s.intersection(right.s)) == 0:
                node.tag = 'S'
            else: 
                node.tag = 'D'
                node.n_dup += 1
    tree.n_dup = tree.root.n_dup


def decompose(tree, max_only=False, no_subsets=False):
    """
    Decomposes a tagged tree, by separating clades at duplication vetices

    NOTE: must be run after 'tag()'

    Parameters
    ----------
    tree: tagged treeswift tree
    max_only: return only the single large
    no_subsets: filters out duplicate clades that have leafsets which are subsets of their counterpart

    Returns result of the decomposition as a list of trees
    """
    out = []
    root = tree.root
    for node in tree.traverse_postorder(leaves=False):
        if node.tag == 'D':
            # trim off smallest subtree (i.e. subtree with least species)
            [left, right] = node.child_nodes()
            delete = left if len(left.s) < len(right.s) else right
            if not max_only and not (right.s.issubset(left.s) and no_subsets):
                out.append(tree.extract_subtree(delete))
            node.remove_child(delete)
    tree.suppress_unifurcations() # all the duplication nodes will be unifurcations
    out.append(tree)
    return out


def trim(tree, smallest=True):
    """
    Trims duplicate leaves under ever duplication vertex.

    NOTE: must be run after 'tag()'

    Parameters
    ----------
    tree: tagged treeswift tree
    smallest: bool signifying that leaves should be trimmed from
        the smallest clade, otherwise trimmed from the largest

    Returns a single tree with removed leaves
    """
    tree = copy.deepcopy(tree)

    for node in tree.traverse_postorder(leaves=False):
        if node.tag == 'D':
            # trim only duplicate leaves from smallest subsection
            [left, right] = node.child_nodes()
            to_delete = left.s.intersection(right.s)
            delete_from = left if (len(left.s) < len(right.s)) == smallest else right
            for v in delete_from.traverse_postorder():
                if v.s.issubset(to_delete) or (v.is_leaf() and v.label is None):
                    parent = v.get_parent()
                    parent.remove_child(v)
    return tree


def sample(tree, sampling_method):
    """
    Samples from a tagged tree, by taking clades at random at duplication vetices

    NOTE: must be run after 'tag()'

    Parameters
    ----------
    tree: tagged treeswift tree
    sampling_method: defines the number of samples
                "linear" - the number of sample is the same as the duplication node
                "exp" - the number of sample = 2^number of duplication node
                custom method - takes as parameter the number of duplication nodes, and returns the number of samples

    Returns samples as a list of trees
    """
    random.seed(0) # set fixed seed for reproducibility 
    out = []
    root = tree.root
    if sampling_method == 'linear':
        n_sample = tree.n_dup + 1
    elif sampling_method == 'exp':
        n_sample = 2 ** tree.n_dup
    elif sampling_method.isdigit():
        n_sample = int(sampling_method)
    else:
        n_sample = sampling_method(tree.n_dup)
    
    for i in range(n_sample):
        for node in tree.traverse_postorder(leaves=False):
            if node.tag == 'D':
                # deletes one randomly
                [left, right] = node.child_nodes()
                # we want to keep sections with more duplicates more often
                # otherwise we can end up getting the same small tree repeatedly
                bias = (left.n_dup + 0.5) / node.n_dup
                node.delete = left if random.random() > bias else right
                #node.delete = random.choice(node.child_nodes())
                node.remove_child(node.delete)
        out.append(treeswift.read_tree_newick(tree.newick()))
        for node in tree.traverse_preorder(leaves=False):
            if node.tag == 'D':
                node.add_child(node.delete)
    return out


def trivial(newick_str):
    """
    Determines if a newick string represents a trivial tree (tree containing no quartets).

    Parameters
    ----------
    newick_str: newick string

    Returns True if tree contains less than two '('
    """
    count = 0
    for c in newick_str:
        if c == '(':
            count += 1
        if count > 1:
            return False
    return True


def main(args):

    if args.output is None:
        split = args.input.rsplit('.', 1)
        output = split[0] + '-decomp.' + split[1]
    else:
        output = args.output

    # delete existing outgroup file (so you don't append to it)
    outgroup_file_name = args.input.rsplit('.', 1)[0] + '_outgroups.txt'
    if args.outgroups:
        open(outgroup_file_name, 'w').close()

    with open(args.input, 'r') as fi, open(output, 'w') as fo:
        for i, line in enumerate(fi, 1):
            tree = treeswift.read_tree_newick(line)

            if args.remove_in_paralogs:
                num_paralogs = remove_in_paralogs(tree, args.delimiter)

            root, score, ties = get_min_root(tree, args.delimiter)
            tree.reroot(root)
            tag(tree, args.delimiter)

            if args.outgroups:
                og_tree = copy.deepcopy(tree)

            if args.verbose:
                print('Tree ', i, ': Tree has ', len(tree.root.s), ' species.', sep='')
                if args.remove_in_paralogs:
                    print(num_paralogs, 'in-paralogs removed prior to rooting/scoring.')  
                if len(tree.root.s) < 2:
                    print('Uninformative')
                elif tree.n_dup == 0:
                    print('Single-Copy')                 
                else:
                    outgroup = min((len(child.s), child.s) for child in tree.root.child_nodes())                    
                    print('Best root had score ', score, ' with ', tree.n_dup, ' non-terminal' if args.remove_in_paralogs else '',
                        ' duplications; there were ', len(ties), ' ties.\nOutgroup: {',','.join(outgroup[1]),'}', sep='')

            # Choose modes
            if args.trim or args.trim_both:
                out = [trim(tree)]
                if args.trim_both:
                    out.append(trim(tree,False))
            elif args.random_sample:
                out = sample(tree, args.rand_sampling_method)
            else:
                out = decompose(tree, args.max_only, args.no_subsets)

            # Output trees
            num_output = 0
            for t in out:
                unroot(t)
                t.suppress_unifurcations()
                nwck = t.newick()
                if not trivial(nwck) or args.trivial:
                    num_output += 1
                    fo.write(nwck + '\n')
            
            if args.verbose:
                print('Decomposition strategy outputted', num_output, 'non-trivial tree(s).\n' if not args.trivial else 'tree(s).\n')

            # output outgroups
            if args.outgroups and len(og_tree.root.s) >= 2 and og_tree.n_dup >= 1:
                with open(outgroup_file_name, 'a') as outgfile:
                    outgfile.write('Tree ' + str(i) + ':\n')
                    for t in ties:
                        og_tree.reroot(t)
                        outgroup = min((len(child.s), child.s) for child in og_tree.root.child_nodes())
                        outgfile.write('{' + ','.join(outgroup[1]) + '}\n')
            

if __name__ == "__main__":
    sys.setrecursionlimit(10000) # allow for deepcopying really large trees

    parser = argparse.ArgumentParser()

    parser.add_argument("-i", "--input", type=str,
                        help="Input tree list file", required=True)
    parser.add_argument("-o", "--output", type=str,
                        help="Output tree list file")
    parser.add_argument('-d', "--delimiter", type=str, 
                        help="Delimiter separating species name from rest of leaf label", default='_')
    parser.add_argument('-m', '--max_only', action='store_true',
                        help="Only output maximum tree")
    parser.add_argument('-s', '--no_subsets', action='store_true',
                        help="Do not include sections of tree that are subsets")
    parser.add_argument('-t', '--trim', action='store_true',
                        help="Trim duplicate leaves under each duplication event from smallest clade")
    parser.add_argument('-tb', '--trim_both', action='store_true',
                        help="Trim duplicate leaves under each duplication event. Gives two single copy trees (trimming from smallest/largest)")
    parser.add_argument('-r', '--random_sample', action='store_true',
                        help="Samples single-copy trees from gene family trees")
    parser.add_argument('-rm', '--rand_sampling_method', type=str,
                        help="Method to determine the number of samples to take (linear/exp/[number])", default='5')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help="Enables verbose output")
    parser.add_argument("--trivial", action='store_true',
                        help="Include trivial trees (trees without quartets) in output.")
    parser.add_argument("--outgroups", action='store_true',
                        help="Output outgroups to file (including ties)")
    parser.add_argument('-rp', "--remove_in_paralogs", action='store_true',
                        help="Remove in-paralogs before rooting/scoring tree.")

    main(parser.parse_args())
