#!/usr/bin/env python

import os
import web
from web import form
import tempfile
import sys
import simplejson as json
import apt
import re
import socket

sys.path.insert(0,"../")

import logging
from config import Config
from recommender import *
from user import *
from data import DebianPackage

import urllib

class Index:
    def GET(self):
        return render.survey_index()

class About:
    def GET(self):
        return render.about()

class Thanks:
    def POST(self):
        web_input = web.input()
        user_id = web_input['user_id'].encode('utf8')
        with open("./submissions/%s/ident" % user_id,'w') as ident:
            for key in ["name","email","comments"]:
                if web_input.has_key(key):
                    ident.write("%s: %s\n" % (key,web_input[key].encode("utf-8")))
        return render.thanks_id()

class Package:
    def GET(self, pkg):
        result = self.get_details_from_dde(pkg)
        return render_plain.package(result)

    def get_details_from_dde(self, pkg):
        json_source = Config().dde_url % pkg
        json_data = json.load(urllib.urlopen(json_source))
        # parse tags
        tags = self._debtags_list_to_dict(json_data['r']['tag'])
        json_data['r']['tag'] = tags
        # format long description
        json_data['r']['long_description'] = json_data['r']['long_description'].replace(' .\n','').replace('\n','<br />')
        return json_data['r']

    def _debtags_list_to_dict(self, debtags_list):
        """ in:
        	['use::editing',
                'works-with-format::gif',
                'works-with-format::jpg',
                'works-with-format::pdf']
            out:
                {'use': [editing],
                'works-with-format': ['gif', 'jpg', 'pdf']'
                }
        """
        debtags = {}
        subtags = []
        for tag in debtags_list:
            match = re.search(r'^(.*)::(.*)$', tag)
            if not match:
                log.error("Could not parse debtags format from tag: %s", tag)
            facet, subtag = match.groups()
            subtags.append(subtag)
            if facet not in debtags:
               debtags[facet] = subtags
            else:
               debtags[facet].append(subtag)
            subtags = []
        return debtags

class Save:
    def POST(self):
        web_input = web.input()
        logging.info("Saving user evaluation...")
        logging.info(web_input)
        user_id = web_input['user_id'].encode('utf8')
        with open("./submissions/%s/uploaded_file" % user_id) as packages_list:
            pkgs_list = [line.strip() for line in packages_list.readlines()]
        strategy = web_input['strategy']
        logging.debug("Saving evaluation for user %s, strategy %s and packages..."
                      % (user_id,strategy))
        logging.debug(pkgs_list)
        evaluations = {}
        evaluations["poor"] = []
        evaluations["good"] = []
        evaluations["surprising"] = []
        for key, value in web_input.items():
            if key.startswith("evaluation-"):
                evaluations[value.encode('utf8')].append(key.lstrip("evaluation-"))
        output_dir = ("./submissions/%s/%s/" % (user_id,strategy))
        for key,value in evaluations.items():
            with open(os.path.join(output_dir,key),'w') as output:
                for item in value:
                    output.write(item+"\n")
        with open(os.path.join(output_dir,"report"),'w') as report:
            report.write("# User: %s\n# Strategy: %s\n# TP FP\n%d %d\n" %
                         (user_id,strategy,
                          len(evaluations["good"])+len(evaluations["surprising"]),
                          len(evaluations["poor"])))
        if web_input.has_key('continue_button'):
            return Survey().POST()
        elif web_input.has_key('finish_button'):
            return render.thanks(user_id)
        else:
            return render.survey_index()

class Request:
    def __init__(self,web_input,submissions_dir):
        self.strategy = ""
        # Check if it is first round
        if web_input.has_key('user_id'):
            self.user_id = web_input['user_id'].encode('utf8')
            self.user_dir = os.path.join(submissions_dir, self.user_id)
            logging.info("New round for user %s" % self.user_id)
        else:
            self.user_dir = tempfile.mkdtemp(prefix='',dir=submissions_dir)
            self.user_id = self.user_dir.split("/")[-1]
            logging.info("Request from user %s" % self.user_id)
            logging.debug("Created dir %s" % self.user_dir)
        uploaded_file = os.path.join(self.user_dir,"uploaded_file")
        if not os.path.exists(uploaded_file):
            if web_input['pkgs_file'].value:
                lines = web_input['pkgs_file'].file.readlines()
                with open(uploaded_file, "w") as uploaded:
                    uploaded.writelines(lines)
        with open(uploaded_file) as uploaded:
            if uploaded.readline().startswith('POPULARITY-CONTEST'):
                self.user = PopconSystem(uploaded_file,self.user_id)
            else:
                self.user = PkgsListSystem(uploaded_file,self.user_id)

    def __str__(self):
        return "Request %s:\n %s" % (self.user.user_id,
                                     str(self.user.pkg_profile))

    def validates(self):
        self.errors = []
        if not self.user.pkg_profile:
            self.errors.append("No packages list provided.")
        if self.errors:
            return False
        return True

class Survey:
    def __init__(self):
        logging.info("Setting up survey...")
        self.cfg = Config()
        self.rec = Recommender(self.cfg)
        self.submissions_dir = "./submissions/"
        if not os.path.exists(self.submissions_dir):
            os.makedirs(self.submissions_dir)

    def POST(self):
        web_input = web.input(pkgs_file={})
        logging.debug("Survey web_input %s" % str(web_input))
        self.strategies = ["demo_cb","demo_cbd","demo_cbt","demo_col"]#,"demo_colco"]
        request = Request(web_input,self.submissions_dir)
        if not request.validates():
            return render.error_survey()
        else:
            # Check the remaining strategies and select a new one
            old_strategies = [dirs for root, dirs, files in
                              os.walk(os.path.join(self.submissions_dir,
                                                   request.user_id))]
            if old_strategies:
                strategies = [s for s in self.strategies if s not in old_strategies[0]]
                logging.info("Already used strategies %s" % old_strategies[0])
            else:
                strategies = self.strategies
            if not strategies:
                return render.thanks(request.user_id)
            request.strategy = random.choice(strategies)
            logging.info("Selected \'%s\' from %s" % (request.strategy,strategies))
            # Get recommendation
            self.rec.set_strategy(request.strategy)
            prediction = self.rec.get_recommendation(request.user,2).get_prediction()
            logging.info("Prediction for user %s" % request.user_id)
            logging.info(str(prediction))
            strategy_dir = os.path.join(request.user_dir,request.strategy)
            os.makedirs(strategy_dir)
            with open(os.path.join(strategy_dir,"prediction"),"w") as prediction_file:
                for pkg,rating in prediction:
                    prediction_file.write("%s %f.2\n" % (pkg,rating))
            logging.debug("Saved %s/%s prediction to file" %
                          (request.user_id,request.strategy))
            recommendation = [result[0] for result in prediction]

            # Check connection to DDE
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.connect((self.cfg.dde_server,self.cfg.dde_port))
                dde = 1
                s.close()
            except:
                dde =0
                logging.debug("Could not connect to dde")
            # Load packages details
            pkgs_details = []
            for pkg_name in recommendation:
                logging.info("Getting details of package %s" % pkg_name)
                pkg = DebianPackage(pkg_name)
                if dde:
                    pkg.load_details_from_dde(self.cfg.dde_server,self.cfg.dde_port)
                else:
                    pkg.load_details_from_apt()
                pkgs_details.append(pkg)
            if pkgs_details:
                logging.info("Rendering survey slide...")
                return render.survey(pkgs_details, request)
            else:
                return render.error_survey()

def add_global_hook():
    g = web.storage({"counter": "1"})
    def _wrapper(handler):
        web.ctx.globals = g
        return handler()
    return _wrapper

render = web.template.render('templates/', base='layout', globals={'hasattr':hasattr})
render_plain = web.template.render('templates/')

urls = ('/',   		        'Index',
        '/survey',          'Survey',
        '/apprec',          'Survey',
        '/thanks',   		'Thanks',
        '/save',   		    'Save',
        '/thanks',   		'Thanks',
        '/about',           'About',
        '/package/(.*)',  	'Package'
       )

web.webapi.internalerror = web.debugerror

if __name__ == "__main__":
    cfg = Config()
    apprec = web.application(urls, globals())
    apprec.add_processor(add_global_hook())
    apprec.run()
