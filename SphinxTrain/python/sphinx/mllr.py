#!/usr/bin/env python

"""
Adapt acoustic models using maximum-likelihood linear regression.

This module implements single-class mean and variance adaptation using
MLLR as described in M.J.F. Gales & P.C. Woodland, "Mean and Variance
Adaptation within the MLLR Framework", Computer Speech and Language,
vol. 10, pp 249-264.

TODO: Multiple regression classes.
"""

# Copyright (c) 2006 Carnegie Mellon University
#
# You may copy and modify this freely under the same terms as
# Sphinx-III

__author__ = "David Huggins-Daines <dhuggins@cs.cmu.edu>"
__version__ = "$Revision $"

import numpy as np

import sys
import s3gaucnt
import s3gau
import getopt
import s3lda

def estimate_mllr_mean(stats, inmean, invar):
    """
    Estimate an MLLR transformation of the means based on observed
    statistics.
    
    This function calculates an MLLR transformation W (an n by n+1
    matrix) which, when applied to C{inmean}, maximizes the likelihood
    of the data as represented by C{stats}.

    Currently this does only one class and one stream, but it will
    promptly be extended once the "learning exercise" is over.

    @param stats: Observation counts, as returned
                  by C{sphinx.s3gaucnt.accumdirs}
                  or C{sphinx.s3gaucnt.accumdirs_full}.
    @type stats: sphinx.s3gaucnt.S3GauCnt
    @param inmean: Input mean parameters
    @type inmean: sphinx.s3gau.S3Gau
    @param invar: Input diagonal covariance parameters
    @type inmvar: sphinx.s3gau.S3Gau
    @return: MLLR transformation
    @rtype: numpy.ndarray
    """
    ndim = inmean.veclen[0]

    # Collection of G matrices
    G = np.zeros((ndim, ndim+1, ndim+1))
    # Z matrix (for the single class and stream)
    Z = np.zeros((ndim, ndim+1))
    # W matrix
    W = np.zeros((ndim, ndim+1))
    # Actual mean and variance parameters
    m = inmean.getall()
    v = invar.getall()
    # Observation counts
    vc = stats.getvars()
    mc = stats.getmeans()
    dc = stats.getdnom()
    # One-class MLLR: just sum over all densities
    for i in range(0, means.n_mgau):
        for k in range(0, means.density):
            # Extended mean vector
            xmean = np.concatenate(1, m[i][0][k])
            # Inverse variance (also use only the diagonal)
            invvar = v[i][0][k]
            if len(invvar.shape) > 1:
                invvar = np.diag(invvar)
            invvar = 1./invvar.clip(0,1e-5)
            # Sum of posteriors (i.e. sum_t L_m_r(t))
            dnom = dc[i,0,k]
            # Sum of mean statistics
            obsmean = mc[i][0][k]
            
            for l in range(0, ndim):
                G[l] += dnom * invvar[l] * np.outer(xmean, xmean)
            Z[l] += np.outer(invvar * obsmean, xmean)
    # Now solve for the rows of W
    for i in range(0, ndim):
        W[i] = np.linalg.solve(G[i], Z[i])
    return W

def estimate_mllr_variance(stats, inmean, invar, W):
    """
    Estimate an MLLR transformation of the variances based on observed
    statistics.
    
    This function calculates an MLLR transformation H (an n by n
    matrix) which maximizes the likelihood of the data as represented
    by C{stats}, when applied to the inverse Cholesky factor of the
    covariance matrix B as B^T H B.  For diagonal covariances this
    reduces to a scaling of the variance by the diagonals of H, since
    the diagonal b = (sqrt(var^{-1}))^{-1} = var^{0.5}.

    Note that this function will raise an exception if -2passvar yes
    was enabled when collecting the observation counts, since it
    requires them to consist of the sum of the outer products of the
    observation vectors scaled by their posterior probabilities,
    (L_m_r(t)o(t)o(t)^T in Cambridge papers).

    Currently this does only one class and one stream, but it will
    promptly be extended once the "learning exercise" is over.

    @param stats: Observation counts, as returned
                  by C{sphinx.s3gaucnt.accumdirs}
                  or C{sphinx.s3gaucnt.accumdirs_full}.
    @type stats: sphinx.s3gaucnt.S3GauCnt
    @param inmean: Input mean parameters
    @type inmean: sphinx.s3gau.S3Gau
    @param invar: Input covariance parameters
    @type inmvar: sphinx.s3gau.S3Gau
    @param W: Previously computed MLLR transformation of means
    @ptype W: numpy.ndarray
    @return: MLLR transformation of variances
    @rtype: numpy.ndarray
    """
    if stats.pass2var:
        raise RuntimeException, "Statistics using -2passvar yes are not allowed"
    ndim = inmean.veclen[0]
    # Output matrix H
    H = np.zeros((ndim, ndim))
    # Actual mean and variance parameters
    m = inmean.getall()
    v = invar.getall()
    # Observation counts
    vc = stats.getvars()
    mc = stats.getmeans()
    dc = stats.getdnom()
    # One-class MLLR: just sum over all densities
    norm = 0
    for i in range(0, means.n_mgau):
        for k in range(0, means.density):
            # Extended mean vector
            xmean = np.concatenate(1, m[i][0][k])
            # Transform it
            mean = np.dot(W, xmean)
            # Calcluate C (Cholesky factor of inverse variance)
            invvar = v[i][0][k].clip(0,1e-5)
            if len(invvar.shape) == 1:
                invvar = np.diag(invvar)
            C = np.linalg.cholesky(invvar)
            # sum(L_m_r o o^T) (obs squared)
            nom = vc[i][0][k]
            # \hat mu_m_r \bar o_m_r^T (cross term 1)
            nom -= np.outer(mean, mc[i][0][k])
            # \bar o_m_r^T \hat mu_m_r^T (cross term 2)
            nom -= np.outer(mc[i][0][k], mean)
            # \mu_m_r \mu_m_r^T sum(L_m_r) (mean squared)
            nom += np.outer(mean, mean) * dc[i][0][k]
            # Multiply in Cholesky factors and accumulate
            H += np.dot(np.dot(C, nom), C.T)
            # Accumulate normalizer
            norm += dc[i][0][k]
    return H / norm

if __name__ == '__main__':
    def usage():
        sys.stderr.write("Usage: %s INMEAN INVAR OUTMEAN OUTVAR ACCUMDIRS...\n" % sys.argv[0])

    try:
        opts, args = getopt.getopt(sys.argv[1:], "hl:", ["help", "lda="])
    except getopt.GetoptError:
        usage()
        sys.exit(2)
    if len(args) < 5:
        usage()
        sys.exit(2)
    ldafn = None
    for o, a in opts:
        if o in ('-h', '--help'):
            usage()
            sys.exit()

    inmean = s3gau.open(args[0])
    invar = s3gau.open(args[1])
    accumdirs = args[4:]
    stats = s3gaucnt.accumdirs(accumdirs)

    mllr = estimate_mllr(stats, inmean, invar)
