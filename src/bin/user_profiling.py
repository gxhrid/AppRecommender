#!/usr/bin/env python
"""
    user_profiling - example script for testing user profiling
"""
__author__ = "Tassia Camoes Araujo <tassia@gmail.com>"
__copyright__ = "Copyright (C) 2011 Tassia Camoes Araujo"
__license__ = """
    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import sys
sys.path.insert(0,'../')
import user
import xapian

repo = xapian.Database("/home/tassia/.app-recommender/axi_programs")
user = user.LocalSystem()
with open("/home/tassia/.app-recommender/filters/debtags") as tags:
    valid_tags = [line.strip() for line in tags if not line.startswith("#")]
size = 20

print "\nTF-IDF profiles"
print "\nby tag: ", user.content_profile(repo,"tag",size,valid_tags)
print "\nby desc: ", user.content_profile(repo,"desc",size)
print "\nmix:", user.content_profile(repo,"mix",size,valid_tags)
print "\nhalf", user.content_profile(repo,"half",size,valid_tags)

print "\nEset profile"
print "\nby tag: ", user.content_profile(repo,"tag_eset",size,valid_tags)
print "\nby desc:", user.content_profile(repo,"desc_eset",size)
print "\nmix: ", user.content_profile(repo,"mix_eset",size,valid_tags)
print "\nhalf", user.content_profile(repo,"half_eset",size,valid_tags)
