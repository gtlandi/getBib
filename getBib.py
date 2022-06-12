# Might need to install the packages below using
# "pip install urllib"
#  and
# "pip install arxiv"
#  and
# "pip install unidecode"
#  and
# "pip install Levenshtein"
#  and
# "pip install json"

import urllib.request
import arxiv
import re
import unidecode
import json
from urllib.error import HTTPError
from urllib.parse import quote_plus, urlencode
from urllib.request import urlopen, Request
from Levenshtein import ratio, matching_blocks, editops
import string

######################################################
#
#
#   DETERMINES THE KIND OF INPUT (ARXIV, DOI, WEBSITE, &C)
#
#
######################################################
def identifyInput(string):

    # OLD ARXIV CODES
    old_arxiv_identifiers = ['astro-ph', 'cond-mat', 'gr-qc', 'hep-ex', 'hep-lat', 'hep-ph',
                             'hep-th', 'math-ph', 'nlin', 'nucl-ex', 'nucl-th', 'physics', 'quant-ph', 'math']
    for old in old_arxiv_identifiers:
        if (old + '/' in string):
            res =  re.findall(old + '/[0-9]{5,}', string)
            if len(res) != 0:
                return 'arxiv', res[0]

    # DOI
    doi = re.findall('10\.[0-9]{4,5}/[\s\S]*', string)
    if len(doi) != 0:
        return 'doi', doi[0]


    # REGULAR ARXIV CODE (AFTER 2007)
    arxiv = re.findall('[0-9]{4}\.[0-9]{4,}', string)
    if len(arxiv) != 0:
        return 'arxiv', arxiv[0]


    # TITLE
    if ' ' in string:
        return 'title', string


    # WEBSITE
    if ('http' in string) or ('www' in string) or ('.org' in string) or ('.com' in string):
        if 'nature' in string:
            attempt = re.findall('s[0-9]{5}-[0-9]{3}-[0-9]{5}[\s\S]*', string)
            if len(attempt) > 0:
                return 'doi', '10.1038/' + attempt[0]
            else:
                print("failed: looks like a Nature webpage, but couldn't extract DOI")
                return 'fail', 'nature website'


        if 'quantum-journal' in string:
            attempt = re.findall('q-[0-9]{4}-[0-9]{2}-[0-9]{2}-[0-9]{3}', string)
            if len(attempt) > 0:
                return 'doi', '10.22331/' + attempt[0]
            else:
                print("failed: looks like a quantum-journal webpage, but couldn't extract DOI")
                return 'fail', 'quantum-journal website'

        return 'fail', 'generic website'

    else:
        print('failed: looks like a code, but it is not a DOI or an arXiv identifier')
        return 'fail', 'code'


######################################################
#
#
#   TITLE-RELATED FUNCTION
#   ATTEMPTS TO RETURN THE DOI OR arXiv GIVEN A PAPER TITLE
#   adapted from https://github.com/OpenAPC/openapc-de/blob/master/python/import_dois.py
#
#
######################################################
def title_2_doi(title):

    api_url = "https://api.crossref.org/works?"
    params = {"rows": "20", "query.bibliographic": title}
    url = api_url + urlencode(params, quote_via=quote_plus)
    request = Request(url)

    try:
        ret = urlopen(request)
        content = ret.read()
        data = json.loads(content)
        items = data["message"]["items"]
        most_similar = {
                "crossref_title": "",
                "similarity": 0,
                "doi": ""
                }
        for item in items:
            if "title" not in item:
                continue
            title = item['title'].pop()

            result = {
                "crossref_title": title,
                "similarity": ratio(title.lower(), params["query.bibliographic"].lower()),
                "doi": item["DOI"]
            }
            if most_similar["similarity"] < result["similarity"]:
                most_similar = result

        if most_similar['similarity'] < 0.92:
            print('Found a match, but similarity is not looking great.')
        return most_similar
    except HTTPError as httpe:
        return 'fail', 0


######################################################
#
#
#   DOI FUNCTIONS
#   DOI supported content types: https://citation.crosscite.org/docs.html
#
#
######################################################

# RETURNS BIBTEX
def DOI_2_bib(doi):
    doi_req = urllib.request.Request('http://dx.doi.org/' + doi)
    doi_req.add_header('Accept', 'application/x-bibtex')
    with urllib.request.urlopen(doi_req) as f:
        output = f.read().decode()
        year = re.findall('_[0-9]{4}', output)[0][1:]
        return re.sub('_[0-9]{4}', year, output, count = 1)

# RETURNS A FORMATTED CITATION
def DOI_2_formatted(doi):
    doi_req = urllib.request.Request('http://dx.doi.org/' + doi)
    doi_req.add_header('Accept', 'text/x-bibliography')
    with urllib.request.urlopen(doi_req) as f:
        output = f.read().decode()
        return output

# RETURNS A DICTIONARY WITH A BUNCH OF INFORMATION
def DOI_2_dict(doi):
    doi_req = urllib.request.Request('http://dx.doi.org/' + doi)
    doi_req.add_header('Accept', 'application/vnd.citationstyles.csl+json')

    with urllib.request.urlopen(doi_req) as f:
        output = f.read().decode()
        output = json.loads(output)

    # page
    if 'article-number' in output.keys():
        page = str(output['article-number'])
    elif 'page' in output.keys():
        page = str(output['page'])
    else:
        page = ''


    # year
    if 'published-online' in output.keys():
        year = str(output['published-online']['date-parts'][0][0])
    elif 'published' in output.keys():
        year = str(output['published']['date-parts'][0][0])
    else:
        year = ''

    authors = []
    for aut in output['author']:
        if 'given' in aut.keys():
            authors.append(aut['given'] + ' ' + aut['family'])
        else:
            authors.append(aut['family'])

    if 'volume' in output:
        volume = str(output['volume'])
    else:
        volume = ''

    if 'title' in output:
        title = str(output['title'])
    else:
        title = ''

    if 'URL' in output:
        URL = str(output['URL'])
    else:
        URL = ''

    if 'container-title' in output:
        journal = str(output['container-title'])
    else:
        journal = ''

    return {
        'authors': authors,
        'doi': doi,
        'title': title,
        'volume': volume,
        'page': page,
        'year': year,
        'publisher_url': URL,
        'journal': journal,
        'formatted_citation': DOI_2_formatted(doi),
        'bib': DOI_2_bib(doi)
    }

######################################################
#
#
#   arXiv FUNCTIONS
#
#
######################################################

# CONVERTS arXiv ID TO BIBTEX
# If the arxiv search returns a DOI, then bib is taken from the DOI API.
# Otherwise, it is formatted using the information in the arXiv API.
def arXiv_2_bib(ID):
    search = arxiv.Search(id_list=[ID])
    paper = next(search.results())
    doi = paper.doi
    try:
        return DOI_2_bib(doi)
    except:
        author_list = ' and '.join([str(author) for author in paper.authors])
        citation_key = str(paper.authors[0]).split(' ')[-1] + str(paper.published.year)
        citation_key = unidecode.unidecode(citation_key)
        return f'''@article{{{citation_key},
         title = {{{paper.title}}},
         author = {{{author_list.strip()} }},
         year = {{{paper.published.year}}},
         eprint = {{{paper.get_short_id()}}},
         archivePrefix = {{arXiv}},
         primaryClass ={{{paper.categories[0]}}}
        }}'''


# RETURNS A DICTIONARY WITH ALL INFORMATION AVAILABLE IN THE arXiv API
def arXiv_2_dict(ID):
    search = arxiv.Search(id_list=[ID])
    paper = next(search.results())

    fc = ', '.join([aut.name for aut in paper.authors])
    fc = fc + ' "' + paper.title + '," ' + str(paper.published.year) + '. ' + 'https://arxiv.org/abs/' + ID
    return {
        'authors': [aut.name for aut in paper.authors],
        'doi': paper.doi,
        'title': paper.title,
        'year': str(paper.published.year),
        'pdf_url': (paper.pdf_url)[:-2],
        'arXiv': ID,
        'arXiv_url': 'https://arxiv.org/abs/' + ID,
        'volume': '',
        'page': '',
        'journal': '',
        'publisher_url': '',
        'formatted_citation': fc,
        'bib': arXiv_2_bib(ID)
    }



######################################################
#
#
#   WRAPPER FUNCTION FOR GETTING THE BIBLIOGRAPHY
#
#
######################################################
def getBib(string):

    typ, key = identifyInput(string)

    if typ == 'title':
        try:
            doi = title_2_doi(key)['doi']
            return DOI_2_bib(doi)
        except:
            print('Title search + DOI API resulted in failure')

    elif typ == 'doi':
        try:
            return DOI_2_bib(key)
        except:
            print('DOI API resulted in failure. Sometimes this happens for papers that are very new.')

    elif typ == 'arxiv':
        try:
            return arXiv_2_bib(key)
        except:
            print('arXiv API resulted in failure')


######################################################
#
#
#   WRAPPER FUNCTION FOR GETTING THE FULL DICTIONARY
#
#
######################################################
def getDict(string):
    typ, key = identifyInput(string)

    if typ == 'title':
        try:
            return getDict(title_2_doi(key)['doi'])
        except:
            print('Title + DOI search resulted in failure.')

    elif typ == 'doi':
        try:
            doiDict = DOI_2_dict(key)
        except:
            print('DOI dictionary search resulted in failure.')
            return 'fail'

        # Try to add additional info from the arXiv
        try:
            search = arxiv.Search(query=doiDict['title'])
            paper = next(search.results())
            doiDict['pdf_url'] = (paper.pdf_url)[:-2]
            doiDict['arXiv'] = (paper.get_short_id())[:-2]
            doiDict['arXiv_url'] = 'https://arxiv.org/abs/' + doiDict['arXiv']
        except:
            doiDict['pdf_url'] = ''
            doiDict['arXiv'] = ''
            doiDict['arXiv_url'] = ''

        return doiDict

    elif typ == 'arxiv':
        try:
            adict = arXiv_2_dict(key)
        except:
            print('arXiv dictionary search resulted in failure.')
            return 'fail'

        # if arXiv also found a DOI, use dictionary information from DOI instead
        if not adict['doi'] == None:
            try:
                doiDict = getDict(adict['doi'])
                doiDict['pdf_url'] = adict['pdf_url']
                doiDict['arXiv'] = adict['arXiv']
                doiDict['arXiv_url'] = 'https://arxiv.org/abs/' + doiDict['arXiv']
                return doiDict
            except:
                return adict
        else:
            return adict

if __name__ == "__main__":
    string = input("arXiv/DOI/website: ")
    print(getBib(string))
