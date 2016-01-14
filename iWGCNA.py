#!/usr/bin/env python2.7
"""
Perform iterative WGCNA analysis

python dependencies:
  * rpy2

R dependencies:
  * igraph
  * WGCNA
"""

from __future__ import print_function
from __future__ import with_statement

import argparse
import os
import sys
import rpy2.robjects as ro
import pandas as pd
import pandas.rpy.common as pdc
import rSnippets

# Globals
# ========================

r_paste = ro.r['paste']
r_t = ro.r['t']
r_gsub = ro.r['gsub']

# Utilities
# ========================
def restricted_float(x):
    '''
    for argument parsing; restricts float value from 0 to 1
    '''
    x = float(x)
    if x < 0.0 or x > 1.0:
        raise argparse.ArgumentTypeError("%r not in range [0.0, 1.0]"%(x,))
    return x


def warning(prefix, *objs):
    '''
    wrapper for writing to stderr
    '''
    print(prefix, *objs, file=sys.stderr)

def createDir(dirName):
    '''
    check if directory exists in the path, if not create
    '''

    try:
        os.stat(dirName)
    except:
        os.mkdir(dirName)

    return dirName


def parseCommandLineArgs():
    '''
    parse command line args
    '''

    parser = argparse.ArgumentParser(prog="iWGCNA",
                                     description="perform interative WGCNA analysis",
                                     epilog="input file format TBA",
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-i', '--inputFile',
                        metavar='<gene expression file>',
                        help="full path to input gene expression file",
                        required = True)

    parser.add_argument('-o', '--outputFilePath',
                        help="target directory for output files",
                        metavar='<output dir>',
                        default=os.getcwd())

    parser.add_argument('-v', '--verbose',
                        help = 'print status messages',
                        action="store_true")

    # WGCNA parameters
    parser.add_argument('--randomSeed',
                        metavar='<seed>',
                        help="integer for seeding random number generator; see WGCNA manual",
                        type=int,
                        default=12345)

    parser.add_argument('--power',
                        metavar='<power>',
                        help="soft-thresholding power for network construction; see WGCNA manual",
                        type=int,
                        default = 6)

    parser.add_argument('--networkType',
                        metavar='<type>',
                        help="type of adjacency matrix; see WGCNA manual",
                        choices=["signed", "unsigned"],
                        default = "signed")

    parser.add_argument('--maxBlockSize',
                        metavar='<size>',
                        help="maximmum block size for module detection; see WGCNA manual",
                        type=int,
                        default=5000)

    parser.add_argument('--TOMType',
                        metavar='<type>',
                        help="type of topological overlap matrix to be calculated; see WGCNA manual",
                        default="signed",
                        choices=['none', 'signed', 'unsigned'])

    parser.add_argument('--minModuleSize',
                        metavar='<size>',
                        help="minimum module size; see WGCNA manual",
                        default=20,
                        type=int)


    parser.add_argument('--deepSplit',
                        metavar='<split>',
                        help="sensitivity of module detection (cutting of tree height); see WGCNA manual",
                        default=0,
                        type=int,
                        choices = [0, 1, 2, 3, 4])

    parser.add_argument('--minCoreKME',
                        metavar='<cutoff>',
                        help="minimum eigengene connectivity [0, 1.0]; see WGCNA manual",
                        default=0.8,
                        type=restricted_float)

    parser.add_argument('--minCoreKMESize',
                        metavar='<size>',
                        help="minimum number of genes with minCoreKME value to keep module; see WGCNA manual",
                        default=15,
                        type=int)
    parser.add_argument('--allowWGCNAThreads',
                        action="store_true")

    return parser.parse_args()

def readData(inputFile):
    '''
    read gene expression data into a data frame
    '''
    return ro.DataFrame.from_csvfile(inputFile, sep='\t', header=True, row_names = 1)



# iWGCNA
# ========================

# def processPass(a)

def saveRObject(data, objName, path, fileName):

    fileName = path + '/' + fileName
    rSnippets.pyWGCNA.saveObject(data, objName, fileName)

def writeEigengenes(blocks, samples, runId, targetDir):

    return rSnippets.pyWGCNA.processEigengenes(blocks, samples, runId, targetDir)

def processBlocks(data, blocks, runId, targetDir, verbose):
    ''' evaluate blocks by extracting eigengenes,
        calculating eigengene similarities,
        and determining goodness of fit results
    '''
    if verbose:
        warning("Processing BlockwiseResult")

    if verbose:
        warning("Writing Eigengenes")

    eigengenes = writeEigengenes(blocks, data.colnames, runId, targetDir)

    passConverged = False if eigengenes.nrow > 1 else True

    if verbose and passConverged:
        warning("pass converged")

    if not passConverged:
        if verbose:
            warning("Evaluating Fit")
        runConverged = rSnippets.pyWGCNA.evaluateFit(data, blocks, runId, targetDir)

    return (runConverged, passConverged)

def processRun(data, passId, runId,args):
    targetDir= createDir(args.outputFilePath + "/pass" + str(passId) + "/run" + str(runId))

    genes = data.rownames
    samples = data.colnames

    blocks = rSnippets.pyWGCNA.bWGCNA(data,
                                      targetDir,
                                      randomSeed = args.randomSeed,
                                      minCoreKME = args.minCoreKME,
                                      power = args.power,
                                      minModuleSize = args.minModuleSize,
                                      minCoreKMESize = args.minCoreKMESize,
                                      maxBlockSize = args.maxBlockSize,
                                      networkType = args.networkType,
                                      TOMType = args.TOMType,
                                      deepSplit = args.deepSplit,
                                      verbose = args.verbose,
                                      allowWGCNAThreads = args.allowWGCNAThreads)

    saveRObject(blocks, 'blockwiseResult', targetDir, "blockwiseWGCNA-output.RData")

    key = "pass" + str(passId) + "_run" + str(runId)
    return processBlocks(data, blocks, key, targetDir, args.verbose)

def iWGCNA(args):
    runId = 0
    passId = 0

    currentDataFile = args.inputFile
    data = readData(currentDataFile)

    passConverged = False
    while not passConverged:
        passId = passId + 1
        while not passConverged:
            runConverged = False
            runId = runId + 1
            processRun(data, passId, runId,args):

if __name__ == "__main__":

    try:
        args = parseCommandLineArgs()
        createDir(args.outputFilePath)
        iWGCNA(args)

    finally:
        warning("iWGCNA: complete")


__author__ = "Emily Greenfest-Allen"
__copyright__ = "Copyright 2015, University of Pennsylvania"