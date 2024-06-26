#!/usr/bin/env python
# coding: utf-8

import pickle
import pandas as pd
import numpy as np
import os
import mygene
import requests, sys

from sqlalchemy import text

from django.conf import settings
from django.db import connection

from domain.Process.load_data import gid2name_all

server = "http://rest.ensembl.org"
cwd = os.getcwd()

# --- Get database connection aka 'SQLAlchemie engine'
engine = settings.DATABASE_ENGINE


# The data is generated by "map_exons_to_domains.py":
# data=pd.read_csv( 'domain/data/final.csv')

# List of transcripts from genes from Biomart":
# genes=pd.read_csv( 'domain/data/gene_to transcripts.csv')

# #List of transcripts name and discriptions from Biomart":
# gene_info=pd.read_csv( 'domain/data/gene_info.csv')

# invert gid2name_all for every organism
gid2name_all_inverted = {k: {v: k for k, v in v.items()} for k, v in gid2name_all.items()}


def entrez_to_name_online(entrezID):
    mg = mygene.MyGeneInfo()
    out = mg.querymany(entrezID, scopes='entrezgene', fields='symbol', species='human')
    return out[0]['symbol']


def entrez_to_name(entrezID, organism):
    return gid2name_all[organism][entrezID]


def name_to_entrez(name, organism):
    return gid2name_all_inverted[organism][name]


def protein_to_transcript(Ensemble_prID):
    ext = "/lookup/id/" + Ensemble_prID + "?"
    info = req(ext)
    return info["Parent"]


def transcript(transcript_ID, organism):
    # The input transcript ID
    # Outputs
    # Exons: all exons in the transcript
    # D: mapping coding exons to their respective protein domains
    # uniaue domains in the protein

    query = """
            SELECT * 
            FROM exons_to_domains_data_""" + organism + """
            WHERE "Transcript stable ID"=:transcript_id 
            ORDER BY "Exon rank in transcript"
            """

    tdata = pd.read_sql_query(sql=text(query), con=engine, params={'transcript_id': transcript_ID})

    # tdata=tdata.drop(columns=["Unnamed: 0"]).drop_duplicates()
    # df_filter = data['Transcript stable ID'].isin([transcript_ID])
    # tdata=data[df_filter].sort_values(by=['Exon rank in transcript'])

    exons = tdata.drop(columns=["Pfam ID", "Pfam start", "Pfam end"]).drop_duplicates()
    D = tdata[tdata["Pfam ID"].notna()].drop_duplicates()
    p = D["Pfam ID"].unique()
    return exons, D, p


# cool function to search for all transcripts that contains a specific domain in the genome
def domain_search(pfam_id, organism):
    query = """
            SELECT * 
            FROM exons_to_domains_data_""" + organism + """
            WHERE "Pfam ID"=:pfam_id 
            ORDER BY "Exon rank in transcript"
            """
    return pd.read_sql_query(sql=text(query), con=engine, params={'pfam_id': pfam_id})


def req(ext):
    r = requests.get(server + ext, headers={"Content-Type": "application/json"})

    if not r.ok:
        r.raise_for_status()
        sys.exit()
    return r.json()


# used !!
def gene_to_all_transcripts(gene_ID, organism):
    query = """
            SELECT DISTINCT "Transcript stable ID" 
            FROM gene_info_""" + organism + """
            WHERE "Gene stable ID"=:Gene
            """
    tdata = pd.read_sql_query(sql=text(query), con=engine, params={'Gene': gene_ID})["Transcript stable ID"]

    # df_filter = genes['Gene stable ID'].isin([gene_ID])
    # tdata=genes[df_filter]
    # tdata=tdata["Transcript stable ID"].drop_duplicates()

    tdata = tdata.unique()

    return tdata


def Domain_name(Pfam_id):
    with connection.cursor() as cursor:
        # currently this is only domain_domain_human since we only have human data
        cursor.execute("SELECT symbol, Description FROM domain_domain_human WHERE pfam_id = %s", [Pfam_id])
        row = cursor.fetchone()

    if row is None:
        return '-', '-'
    else:
        return row[0], row[1]


# not used now
def gene_to_all_transcripts_online(gene_ID):
    mg = mygene.MyGeneInfo()
    out = mg.querymany(gene_ID, scopes='ensembl.gene', fields='ensembl', species='human')[0]['ensembl']
    try:
        out = out['transcript']
    except TypeError:
        # print('error')
        for output in out:
            if output['gene'] == gene_ID:
                out = output['transcript']
    return out


# used    !!!!


def tranID_convert(Ensemble_transID, organism):
    print('converting ID...', Ensemble_transID)
    query = """
            SELECT * 
            FROM gene_info_""" + organism + """
            WHERE "Transcript stable ID"=:Ensemble_transID 
            """
    tdata = pd.read_sql_query(sql=text(query), con=engine, params={'Ensemble_transID': Ensemble_transID})

    # df_filter = gene_info['Transcript stable ID'].isin([Ensemble_transID])
    # tdata=gene_info[df_filter]

    # No domain or wrong entry
    if len(tdata) == 0: return 0

    try:
        Ensemble_geneID = tdata["Gene stable ID"].unique()[0]

    except TypeError:
        Ensemble_geneID = False
    try:
        tran_name = tdata["Transcript name"].unique()[0]
        gene_name = tran_name.split('-')[0]
    except TypeError:
        tran_name = False
        gene_name = False

    try:
        entrezID = tdata["NCBI gene ID"].unique()[0]
        entrezID = str(int(tdata["NCBI gene ID"].unique()[0]))

    except TypeError:
        entrezID = False

    try:
        gene_description = tdata["Gene description"].unique()[0]


    except TypeError:
        gene_description = False

    return tran_name, gene_name, Ensemble_geneID, entrezID, gene_description


def tranID_convert_online(Ensemble_transID):
    ext = "/lookup/id/" + Ensemble_transID + "?"

    info = req(ext)
    Ensemble_geneID = info["Parent"]
    tran_name = info["display_name"]

    ext = "/xrefs/id/" + Ensemble_geneID + "?"
    info = req(ext)

    for db in info:
        if db['db_display_name'] == 'NCBI gene': break

    entrezID = db["primary_id"]
    gene_name = db["display_id"]
    gene_description = db["description"]
    # print('ID ========',entrezID)
    return tran_name, gene_name, Ensemble_geneID, entrezID, gene_description


def unitpr_to_Ensemble(Protein_ID):
    Protein_ID = Protein_ID.split('%')[0]
    ext = "/xrefs/symbol/homo_sapiens/" + Protein_ID + "?"

    info = req(ext)
    for item in info:
        if item["type"] == "transcript":
            Ensemble_trID = item["id"]
            break
    for item in info:
        if item["type"] == "translation":
            Ensemble_prID = item["id"]
            break

    return Ensemble_trID, Ensemble_prID


def coordinate_to_exonID(gene_id, s1, e1, organism):
    exon_id = []

    query = """
                        SELECT * 
                        FROM exons_to_domains_data_""" + organism + """ 
                        WHERE "Transcript stable ID" IN
                            (SELECT DISTINCT "Transcript stable ID" 
                            FROM gene_info_""" + organism + """ 
                            WHERE "Gene stable ID"=:gene_id )
                        """
    df = pd.read_sql_query(sql=text(query), con=engine, params={'gene_id': gene_id})

    for index, row in df.iterrows():
        s2, e2 = row["Genomic coding start"], row["Genomic coding end"]
        if pd.notna(s2) and pd.notna(e2) and is_overlapping(s1, e1, s2, e2):
            exon_id = row["Exon stable ID"]
            return exon_id

    return exon_id


def is_overlapping(x1, x2, y1, y2):
    return max(x1, y1) <= min(x2, y2)


def interactive_select(pd_interaction):
    Interactiveview_select = {'Original': [], 'High confidence': [], 'Mid confidence': [], 'Low confidence': []}
    pd_interaction['Confidence'] = pd_interaction['Confidence'].str.capitalize()
    # go through pd_interaction and create a dictionary with the select box options
    for index, row in pd_interaction.iterrows():
        if row['Confidence'] == 'Original':
            Interactiveview_select[row['Confidence']].append([row['_'], row['NCBI gene ID'], row['Percentage of lost domain-domain interactions']])
        else:
            Interactiveview_select[row['Confidence'] + " confidence"].append(
                [row['_'], row['NCBI gene ID'], row['Percentage of lost domain-domain interactions']])

    order = {'Original': 3, 'High confidence': 2, 'Mid confidence': 1, 'Low confidence': 0}
    return dict(sorted(Interactiveview_select.items(), key=lambda x: order.get(x[0], 0), reverse=True))