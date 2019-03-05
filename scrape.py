from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
import os
import re
import sys
import time
import pandas as pd
from lxml import html
import ipdb

class counter_class:

    def __init__(self, limit=-1):
        self.count = 0
        self.limit = limit

    def increment(self):
        self.count+=1

class TestMethodMismatchIdentification:

    def __init__(self, excel_input="Input.xlsx", limit=-1):

        # (Check) if chromedriver and chromedriver.exe exists
        # Configure chrome webdriver
        if os.name == 'nt':
            self.driver_path = "./chromedriver.exe"
        else:
            self.driver_path = "./chromedriver"
        os.environ["webdriver.chrome.driver"] = self.driver_path

        # (Check) if ./data/ exists, else create one
        self.cached_list = [os.path.splitext(f)[0] for f in os.listdir("./data")]
        # self.cached_list = [] # uncomment this if you want to regenerate your cache

        # Initialize input dataframe from excel file
        self.input_df = pd.read_excel("./{}".format(excel_input), header=None, usecols=[0,1,2])

        # Make sure input_df has 3 columns: test_id, test_item and test_method
        if self.input_df.shape[1] == 2:
            self.input_df.insert(0,"","")
        elif self.input_df.shape[1] == 3:
            """do nothing"""
        else:
            sys.exit("{} must be an excel file with only 2 or 3 columns ({} detected)".format(excel_input, self.input_df.shape[1]))
        # Rename the columns
        self.input_df.columns = ["test_id","test_item","test_method"]

    def sanitize(self, s):
        """
        'Sanitizes' strings into a more uniform version so that
        they will have a higher chance of being matched together
        """
        s = s.lower().replace(" ", "").replace("-", "").replace(",", "").replace(":", "").replace("&","and").replace("(","").replace(")","").strip()
        # Additional sanitization rules
        s = s.replace("sulphate","sulfate")
        return s

    def substring_check(self, str1, str2):
        """Checks if either string is a substring of the other"""
        return self.sanitize(str1) in self.sanitize(str2) or self.sanitize(str2) in self.sanitize(str1)

    def compare_keywords(self, str1, str2):
        """
        Checks how many keywords in str1 are present in str2
        Any word not inside the exclusion_list is a keyword
        """

        def ssify(stringg):
            """
            All keywords will have an 's' appended to them if they don't already have one
            to make comparisons between plural and singular forms match
            """
            if stringg[-1] != "s":
                return stringg + "s"
            return stringg

        exclusion_list = ['', 'and', '&', 'of', 'or', 'the']
        arr1 = [ssify(self.sanitize(x)) for x in str1.split() if self.sanitize(x) not in exclusion_list]
        arr2 = [ssify(self.sanitize(x)) for x in str2.split() if self.sanitize(x) not in exclusion_list]
        # arr1 = [ssify(self.sanitize(x)) for x in re.split("\s-,;:()", str1) if self.sanitize(x) not in exclusion_list]
        # arr2 = [ssify(self.sanitize(x)) for x in re.split("\s-,;:()", str2) if self.sanitize(x) not in exclusion_list]
        i=0
        for word in arr1:
            if word in arr2:
                i+=1
        return "{}/{}".format(i, len(arr1))

    def refine_search(self, s):
        """
        string s goes through each regex in order, and when it matches the capturing group is returned
        """

        # SS 73 Part 21 -> SS 73
        part = re.compile("(?i)^(.+)\sPart\s.+$").match(s)
        if part: return part.group(1)

        # ATM D546 (ASTM D242) -> ATM D546
        bracket = re.compile("^(.+)\s\(.+\)$").match(s)
        if bracket: return bracket.group(1)

        # BS EN 1744-1 Cl 15.3 -> BS EN 1744-1
        cl = re.compile("(?i)^(.+)\sCl\s.+$").match(s)
        if cl: return cl.group(1)

        # BS EN 1926 Annex A -> BS EN 1926
        annex = re.compile("(?i)^(.+)\sAnnex\s.+$").match(s)
        if annex: return annex.group(1)

        # ASTM D7012 Method C -> ASTM D7012
        method = re.compile("(?i)^(.+)\sMethod\s.+$").match(s)
        if method: return method.group(1)

        # K H Head:Vol.2, Cl 10 -> K H
        head = re.compile("(?i)^(.+)\sHead\s.+$").match(s)
        if head: return head.group(1)

        # K H Head:Vol.2, Cl 10 -> K H Head:
        vol = re.compile("(?i)^(.+)\sVol\s.+$").match(s)
        if vol: return vol.group(1)

        # PS 18 Clause 5.8 -> PS 18
        clause = re.compile("(?i)^(.+)\sClause\s.+$").match(s)
        if clause: return clause.group(1)

        # This ensures that there are at least two words in the string
        if len(s.split()) < 2: return s

        # BS 812-121 -> BS 812
        hyphen = re.compile("^([^-]+)-.+$").match(s)
        if hyphen: return hyphen.group(1)

        # K H Head:Vol.2, Cl 10 -> K H Head
        colon = re.compile("^([^:]+):.+$").match(s)
        if colon: return colon.group(1)

        # ASTM C128 Gravimetric Method -> ASTM C128
        twowords = re.compile("^([A-Z0-9]+\s[A-Z0-9]+)\s.+$").match(s)
        if twowords: return twowords.group(1)

        return s

    def dump_tuples(self, listt):
        """
        Converts a list of tuples into a string
        like so: [(a, b, c), (d, e, f)]  ->  "a| b| c  ~  d| e| f"
        """
        stringg = ""
        for t1 in listt:
            for t2 in t1:
                stringg+="{}| ".format(t2)
            stringg = stringg[0:-2] + "  ~  "
        return stringg[0:-5]

    def prep_driver(self):
        """
        Sets up a webdriver instance of chrome and navigates to the appropriate webpage.
        Returns the driver instance for assignment to a variable (so it doesn't get garbage collected on function exit)
        """
        drv = webdriver.Chrome(self.driver_path)

        # Navigate to SIMS website
        drv.get('https://sims.me.exova.com/SIMS/SIMS-MVC/DashBoard/Index')

        # Enter username and password
        selectElem=drv.find_element_by_id("UserName")
        selectElem.clear()
        selectElem.send_keys("username")
        selectElem=drv.find_element_by_name("pwd")
        selectElem.clear()
        selectElem.send_keys("password")

        # Press 'Login'
        selectElem=drv.find_element_by_xpath('//*[@id="LoginMain"]/div/div[3]/form/button')
        selectElem.click()

        # Navigate to test method section
        drv.get('https://sims.me.exova.com/SIMS/SIMS-MVC/Product/Index#ProductSearchGrid')

        #Expand 'Test Search'
        selectElem=drv.find_element_by_xpath('//a[@href="#ProductSearchGrid"]')
        selectElem.click()
        return drv

    def search(self, method):
        """
        Searches a test method and records the results in a dataframe
        It will use any existing cached results if they exist,
        else it will perform the search and cache those results
        """

        # Windows prohibits these reserved characters in file names, so replace them with some other allowed characters
        method_filename = method.replace("<","..").replace(">",".-").replace(":",".+").replace("\"","-.").replace("/","--").replace("\\","-+").replace("|","+.").replace("?","+-").replace("*","++").replace(",","...")

        # if cached results for the method search already exists, return it instead of doing the search again
        if method_filename in self.cached_list:
            print("")
            # if the csv file is empty, return an empty dataframe instead (to avoid exception when parsing an empty csv file)
            if os.path.getsize("./data/{}.csv".format(method_filename)) > 0:
                return pd.read_csv("./data/{}.csv".format(method_filename), header=None, index_col=None, escapechar="|")
            else:
                return pd.DataFrame()

        # if an instance of a web driver does not exist, create one
        try:
            self.driver.current_url
        except:
            self.driver=self.prep_driver()
        driver = self.driver

        # Clear the search field
        selectElem=driver.find_element_by_xpath('//*[@id="ProductSearch"]/div[1]/div/table/thead/tr[2]/th[3]/span/span/span/input')
        selectElem.clear()
        selectElem.send_keys(Keys.ENTER)
        time.sleep(1)

        # Search the method
        selectElem=driver.find_element_by_xpath('//*[@id="ProductSearch"]/div[1]/div/table/thead/tr[2]/th[3]/span/span/span/input')
        selectElem.clear()
        selectElem.send_keys(method.strip())
        selectElem.send_keys(Keys.ENTER)
        selectElem=driver.find_element_by_xpath('//*[@id="ProductSearch"]/div[2]').click()
        if method == "BS EN":
            time.sleep(8) #BS EN results takes a LOONG time to load, allocate more waiting time before reading the table
        time.sleep(2)

        # Obtain the result table from the page
        soup = BeautifulSoup(driver.page_source, features="lxml")
        t1 = soup.find("div", {"id":"ProductSearch"}).find("div", {"class":"k-grid-content"}).find("table").find("tbody")

        # Send result table's html to a file for debugging purposes
        # with open("searchresults.html", "w") as file:
        #     file.write(str(t1.prettify()))

        # Transcribe the html table into a dataframe
        tbl_list = []
        tmp_list = []
        for row in t1.findAll("tr"):
            i = 0
            tmp_list = []
            for cell in row.findAll("td"):
                # Get only the first three columns, which are: test id, test item and test method
                if (i >= 3):
                    break
                else:
                    i += 1
                    #print(i)
                    tmp_list.append(cell.text.strip())
            #print(tmp_list)
            tbl_list.append(tmp_list)
        temp_df = pd.DataFrame(tbl_list)

        # cache the results of this search into a csv file and update the cached_list
        temp_df.to_csv("./data/{}.csv".format(method_filename), header=None, index=None, escapechar="|")
        self.cached_list.append(method)
        print("")

        return temp_df

    def verify_single_entry(self, srs, test_item):
        """
        Takes in a single entry from a table (in the form of a pandas Series)
        and checks if it matches the test_item
        """
        # res_id     = srs[0]
        # res_item   = srs[1]

        # # if the test_item string matches the res_item string perfectly, return the res_id
        # if self.sanitize(res_item) == self.sanitize(test_item):
        #     print("Perfect Match: {} | {}".format(res_item, test_item))
        #     return res_id
        # # else if either of the item strings are a substring of the other, also return the res_id
        # elif self.substring_check(res_item, test_item):
        #     print("{} | {}".format(res_item, test_item))
        #     return res_id
        # # else return the res_id anyway, followed by the res_item string for manual verification later
        # else:
        #     print("{} | {}".format(res_item, test_item))
        #     return "{}| {}".format(res_id, res_item)
        print("You should never reach this part of verify_single_entry()")
        return "You should never reach this part of verify_single_entry()"

    def filter_and_verify_multiple_entries(self, res, test_item, test_method):
        """
        Accepts a dataframe 'res'
        Filters that dataframe by items that match the test_item
        Returns data from matching rows as a single string
        """
        perfect_matches = []
        partial_matches = []
        all_entries = []
        for i in range(len(res)):

            res_id     = res.iloc[i][0]
            res_item   = res.iloc[i][1]
            res_method = res.iloc[i][2]

            if self.sanitize(res_item) == self.sanitize(test_item):
                perfect_matches.append( (res_id, res_item, res_method) )
            elif self.substring_check(res_item, test_item):
                partial_matches.append( (res_id, res_item, res_method) )
            all_entries.append( (res_id, res_item, res_method) )

        if len(perfect_matches) == 1:
            res_id     = perfect_matches[0][0]
            res_item   = perfect_matches[0][1]
            if self.sanitize(res_item) == self.sanitize(test_item):
                print("Perfect Match: {} | {}".format(res_item, test_item))
                return res_id
            else:
                print("{} | {}".format(res_item, test_item))
                return res_id
            # srs = pd.Series(perfect_matches[0])
            # return self.verify_single_entry(srs, test_item)
        elif len(perfect_matches) > 1:
            stringg = self.dump_tuples(perfect_matches)
            print("{} Perfect Matches".format(len(perfect_matches)))
            print("{}".format(stringg))
            return stringg
        else: # len(perfect matches) == 0
            if len(partial_matches) == 1:
                res_id     = partial_matches[0][0]
                res_item   = partial_matches[0][1]
                if self.sanitize(res_item) == self.sanitize(test_item):
                    print("Perfect Match: {} | {}".format(res_item, test_item))
                    return res_id
                else:
                    print("{} | {}".format(res_item, test_item))
                    return res_id
                # srs = pd.Series(partial_matches[0])
                # return self.verify_single_entry(srs, test_item)
            elif len(partial_matches) > 1:
                stringg = self.dump_tuples(partial_matches)
                print("{} Partial Matches".format(len(perfect_matches)))
                print("{}".format(stringg))
                return stringg
            elif len(all_entries) <= 3:
                stringg = self.dump_tuples(all_entries)
                print("Only {} results".format(len(all_entries)))
                print("{}".format(stringg))
                return stringg
            else: # len(partial matches) == 0
                # If perfect and substring matches fail, it's time to bring out the big boy pants
                # For each row, tally how many keywords from test_item appear in res_item
                # Return the results that have the highest number of keyword matches
                all_entries_detailed = []
                for i in range(len(res)):

                    res_id     = res.iloc[i][0]
                    res_item   = res.iloc[i][1]
                    res_method = res.iloc[i][2]

                    fraction = self.compare_keywords(test_item, res_item) # a string representing how many keywords turn up e.g. 3/5
                    rgx = re.compile("(\d+)/(\d+)")
                    percentage = int(rgx.match(fraction).group(1)) / int(rgx.match(fraction).group(2)) # `fraction` variable expressed as a decimal
                    all_entries_detailed.append( (res_id, res_item, res_method, test_item, test_method, fraction, percentage) )

                df = pd.DataFrame(all_entries_detailed)

                max_percentage = max(df[6]) # the highest number of keyword matches in the table
                keyword_matches = []
                if max_percentage == 0:
                    return "Searched for \"{}\" with {} hits but no item matches \"{}\"".format(test_method, len(res), test_item)
                else: # max_percentage != 0
                    for i in range(len(df)):
                        res_id     = df.iloc[i][0]
                        res_item   = df.iloc[i][1]
                        res_method = df.iloc[i][2]
                        percentage = df.iloc[i][6]
                        if percentage == max_percentage:
                            keyword_matches.append( (res_id, res_item, res_method) )
                    stringg = self.dump_tuples(keyword_matches)
                    print("{} Keyword Matches".format(len(keyword_matches)))
                    print("{}".format(stringg))
                    return stringg
        print("You should never reach this part of filter_and_verify_multiple_entries()")
        return "You should never reach this part of filter_and_verify_multiple_entries()"

    def obtain_id(self, test_id, test_item, test_method, counter, recursion_level=0):
        """
        Searches for test_method and heuristically decides which is the correct test_id from the results.
        """
        if recursion_level == 0:
            counter.increment()

        # limit is used to check how many total iterations are needed
        # counter.count tracks how many of those iterations have already been completed
        limit = counter.limit if counter.limit>0 else self.input_df.shape[0]

        # If limit is non-zero, stop searching when the counter hits the limit
        # This is to avoid searching the entire document during testing since the web searches can be quite slow
        if counter.limit>0 and counter.count>counter.limit:
            return "blank"

        # If the 'test_id' column of input_df isn't already filled with a test id then do a search
        if pd.notnull(test_id) and re.compile("^[A-Z0-9]{6}.*$|^Search.+$").match(test_id):
            return test_id
        else:
            res=self.search(test_method.strip())

        # If there are 0 results, refine the test_method string and call obtain_id() again recursively. If the test_method cannot be further refined (meaning the refine_search() method returns the same string) then there really are no hits
        if res.shape[0] == 0:
            test_method_refined = self.refine_search(test_method.strip())
            if test_method_refined == test_method:
                print("[{}/{}] Search of \"{}\" had no hits".format(counter.count, limit, test_method.strip()))
                return "Search of \"{}\" had no hits".format(test_method.strip())
            else:
                print("[{}/{}] Initial search of \"{}\" yielded 0 hits. Refining search to \"{}\"" .format(counter.count ,limit ,test_method.strip() ,test_method_refined))
                return self.obtain_id(test_id, test_item, test_method_refined, counter, recursion_level=recursion_level+1)

        # Print progress
        print("[{}/{}] hits: {} ({},{})" .format(counter.count ,limit ,res.shape[0] ,test_method.strip() ,test_item.strip()))
        with pd.option_context('display.max_rows', None, 'display.max_columns', None, 'display.max_colwidth', -1): print(res)

        if res.shape[0] == 1:
            res_id     = res.iloc[0][0]
            res_item   = res.iloc[0][1]
            if self.sanitize(res_item) == self.sanitize(test_item):
                print("Perfect Match: {} | {}".format(res_item, test_item))
                return res_id
            else:
                print("{} | {}".format(res_item, test_item))
                return res_id
            # res_id     = res.iloc[i][0]
            # res_item   = res.iloc[i][1]
            # res_method = res.iloc[i][2]
            # return self.verify_single_entry(res.iloc[0], test_item)
        else: # res.shape[0] > 1
            return self.filter_and_verify_multiple_entries(res, test_item, test_method)
        print("you should never reach this part of obtain_id()")
        return "you should never reach this part of obtain_id()"

    def execute(self, excel_output="Output.xlsx"):
        counter = counter_class()
        self.input_df['test_id'] = self.input_df.apply(
                lambda row: self.obtain_id(row['test_id'], row['test_item'], row['test_method'], counter)
                ,axis=1
                )
        # export the resultant dataframe to excel
        self.input_df.to_excel("./{}".format(excel_output), header=None, index=None)

if __name__ == '__main__':
    tmmi = TestMethodMismatchIdentification()
    tmmi.execute()
