#!/usr/bin/python

#  AppRecommender - A GNU/Linux application recommender
#
#  Copyright (C) 2010  Tassia Camoes <tassia@gmail.com>
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.

import commands
import xapian
import logging
import apt

class FilterTag(xapian.ExpandDecider):
    def __call__(self, term):
        """
        Return true if the term is a tag, else false.
        """
        return term[:2] == "XT"

class User:
    """  """
    def __init__(self,item_score,user_id=0,demographic_profile=0):
        """  """
        self.id = user_id
        self.item_score = item_score
        self.pkg_profile = self.item_score.keys()
        self.demographic_profile = demographic_profile

    def items(self):
        return self.item_score.keys()

    def maximal_pkg_profile(self):
        cache = apt.Cache()
        old_profile_size = len(self.pkg_profile)
        for p in self.pkg_profile[:]:     #iterate list copy
            pkg = cache[p]
            if pkg.is_auto_installed:
                self.pkg_profile.remove(p)
        profile_size = len(self.pkg_profile)
        logging.info("Reduced packages profile size from %d to %d." %
                     (old_profile_size, profile_size))

    def axi_tag_profile(self,apt_xapian_index,profile_size):
        terms = []
        for item in self.pkg_profile:
            terms.append("XP"+item)
        query = xapian.Query(xapian.Query.OP_OR, terms)
        enquire = xapian.Enquire(apt_xapian_index)
        enquire.set_query(query)
        rset = xapian.RSet()
        for m in enquire.get_mset(0,30000): #consider all matches
             rset.add_document(m.docid)
        eset = enquire.get_eset(profile_size, rset, FilterTag())
        profile = []
        for res in eset:
            profile.append(res.term)
            logging.debug("%.2f %s" % (res.weight,res.term[2:]))
        return profile

    def txi_tag_profile(self,tags_xapian_index,profile_size):
        return tags_xapian_index.relevant_tags_from_db(self.pkg_profile,
                                                       profile_size)

class LocalSystem(User):
    """  """
    def __init__(self):
        item_score = {}
        dpkg_output = commands.getoutput('/usr/bin/dpkg --get-selections')
        for line in dpkg_output.splitlines():
            pkg = line.split('\t')[0]
            item_score[pkg] = 1
        User.__init__(self,item_score)
