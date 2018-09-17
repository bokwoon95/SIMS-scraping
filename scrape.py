from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
import datetime
import os
import time
import re
import sys
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

        # (Check) if ./data/ exists
        self.cached_list = [os.path.splitext(f)[0] for f in os.listdir("./data")]
        # self.cached_list = []

        # Initialize input dataframe from excel file
        self.input_df = pd.read_excel("./{}".format(excel_input), header=None, usecols=[0,1])

        # Make sure input_df has 3 columns: test_id, test_item and test_method
        if self.input_df.shape[1] == 2:
            self.input_df.insert(0,"","")
            self.input_df.columns = ["test_id","test_item","test_method"]
        elif self.input_df.shape[1] == 3:
            """do nothing"""
        else:
            sys.exit("{} must be an excel file with only 2 or 3 columns ({} detected)".format(excel_input, self.input_df.shape[1]))

    def sanitize(self, s):
        return s.lower().replace(" ", "").replace("-", "").replace(",", "").replace(":", "").strip()

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
        selectElem.send_keys("vignesh.v")
        selectElem=drv.find_element_by_name("pwd")
        selectElem.clear()
        selectElem.send_keys("Adjan2017#")

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
        Searches a test method and returns the results in a dataframe
        It will use any existing cached results if they exist
        """

        method_filename = method.replace(":","..") # Windows forbids filenames with a colon ":", replace those with two dots ".." instead

        # if cached results for the method search already exists, return it instead of doing the search again
        if method_filename in self.cached_list:
            print("")
            print("{} already exists in cached_list".format(method_filename))
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
        time.sleep(2)

        # Obtain the result table from the page
        soup = BeautifulSoup(driver.page_source, features="lxml")
        t1 = soup.find("div", {"id":"ProductSearch"}).find("div", {"class":"k-grid-content"}).find("table").find("tbody")

        # Send result table's html to a file for debugging purposes
        with open("searchresults.html", "w") as file:
            file.write(str(t1.prettify()))

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
        temp_df.to_csv("./data/{}.csv".format(method.replace(":","..")), header=None, index=None, escapechar="|")
        self.cached_list.append(method)
        print("")
        print("{} added to cached_list".format(method.replace(":","..")))

        return temp_df

    def obtain_id(self, test_id, test_item, test_method, counter):
        """
        Searches for test_method and heuristically decides which is the correct test_id from the results.
        """
        counter.increment()
        if counter.count == 4:
            ipdb.set_trace()

        # If limit is non-zero, stop searching when the counter hits the limit
        # This is to speed up the debugging process since the web searches can be quite slow
        if counter.limit>0 and counter.count>counter.limit:
            return "blank"

        # if the 'test_id' column of input_df isn't already filled with a test id then do a search
        if pd.notnull(test_id) and re.compile("[A-Z0-9]{6}").match(test_id):
            return test_id
        else:
            res=self.search(test_method.strip())

        # print progress
        print("[{}/{}] hits: {} ({},{})"
                .format(
                    counter.count
                    ,counter.limit if counter.limit>0 else self.input_df.shape[0]
                    ,res.shape[0]
                    ,test_method.strip()
                    ,test_item.strip()))
        # print hit results
        with pd.option_context('display.max_rows', None, 'display.max_columns', None, 'display.max_colwidth', -1):
            print(res)

        if res.shape[0] == 0:
            return "0 hits"
        elif res.shape[0] == 1:
            return self.filter_A_x(res.iloc[0], test_item)
        elif res.shape[0] > 1:
            res_EXACT_method=res[res[2] == test_method.strip()]
            print("exact hits: {}".format(res_EXACT_method.shape[0]))
            with pd.option_context('display.max_rows', None, 'display.max_columns', None, 'display.max_colwidth', -1):
                print(res_EXACT_method)
            if res_EXACT_method.shape[0] == 1:
                return self.filter_A_x(res_EXACT_method.iloc[0], test_item)
            else:
                res_EXACT_method_EXACT_item = res_EXACT_method[res_EXACT_method[1] == test_item.strip()]
                if res_EXACT_method_EXACT_item.shape[0] > 0:
                    return "E80: everything in res_exactmethod_exactitem"
                else: # if .shape[0] == 0
                    res_EXACT_method_PARTIAL_item = res_EXACT_method[res_EXACT_method[1] == test_item.strip()]
                print("{} exact hits".format(res_EXACT_method.shape[0]))
                return "{} exact hits".format(res_EXACT_method.shape[0])
        else:
            print("{} hits on initial search".format(res.shape[0]))
            return "{} hits".format(res.shape[0])
        print("you should never reach this part of first_pass()")
        return "you should never reach this part of first_pass()"

    def filter_A(self, res, test_item):
        """
        Only accepts a dataframe ('res') of one entry.
        Checks if that dataframe's item matches the test_item
        Returns a string, either the correct id or the id followed by the test_item for manual verification
        res.iloc[x,0]: res_id
        res.iloc[x,1]: res_item
        res.iloc[x,2]: res_method
        """

        # if there are no hits, return "0 hits"
        if res.shape[0] != 1:
            sys.exit("filter_A() only accepts dataframes with one entry!!! Passed in dataframe has {} entries".format(res.shape[0]))
        # if the test_item string matches the hit item string perfectly, return the hit id
        if self.sanitize(res.iloc[0,1]) == self.sanitize(test_item):
            print("Perfect Match: {} | {}".format(res.iloc[0,1], test_item))
            return res.iloc[0,0]
        # else if either of the item strings are a substring of the other, also return the hit id
        elif (self.sanitize(res.iloc[0,1]) in self.sanitize(test_item) or self.sanitize(test_item) in self.sanitize(res.iloc[0,1])):
            print("{} | {}".format(res.iloc[0,1], test_item))
            return res.iloc[0,0]
        # else return the hit id anyway, followed by the hit item string for manual verification later
        else:
            print("{} | {}".format(res.iloc[0,1], test_item))
            return "{}:{}".format(res.iloc[0,0], res.iloc[0,1])
        print("You should never reach this part of filter_A()")
        return "You should never reach this part of filter_A()"

    def filter_A_x(self, srs, test_item):
        """
        res.iloc[x,0]: res_id
        res.iloc[x,1]: res_item
        res.iloc[x,2]: res_method
        """
        # if the test_item string matches the hit item string perfectly, return the hit id
        if self.sanitize(srs[1]) == self.sanitize(test_item):
            print("Perfect Match: {} | {}".format(srs[1], test_item))
            return srs[0]
        # else if either of the item strings are a substring of the other, also return the hit id
        elif (self.sanitize(srs[1]) in self.sanitize(test_item) or self.sanitize(test_item) in self.sanitize(srs[1])):
            print("{} | {}".format(srs[1], test_item))
            return srs[0]
        # else return the hit id anyway, followed by the hit item string for manual verification later
        else:
            print("{} | {}".format(srs[1], test_item))
            return "{}:{}".format(srs[0], srs[1])
        print("You should never reach this part of filter_A()")
        return "You should never reach this part of filter_A()"

    def filter_B(self, res, test_item):
        """
        Accepts a dataframe ('res')
        Filters that dataframe by items that match the test_item
        res.iloc[x,0]: res_id
        res.iloc[x,1]: res_item
        res.iloc[x,2]: res_method
        """
        perfect_matches = []
        partial_matches = []
        for row in res:
            if self.sanitize(res.iloc[0,1]) == self.sanitize(test_item):
                perfect_matches.append((res.iloc[0,0],res.iloc[0,1]))
            elif (self.sanitize(res.iloc[0,1]) in self.sanitize(test_item) or self.sanitize(test_item) in self.sanitize(res.iloc[0,1])):
                partial_matches.append((res.iloc[0,0],res.iloc[0,1]))
        if len(perfect_matches) == 1:
            return
        elif len(perfect_matches) > 1:
            return
        else:
            if len(partial_matches) == 1:
                return
            elif len(partial_matches) > 1:
                return
            else:
                return

    def execute(self):
        counter = counter_class()
        self.input_df['test_id'] = self.input_df.apply(
                lambda row:
                self.obtain_id(
                    row['test_id']
                    ,row['test_item']
                    ,row['test_method']
                    ,counter
                    )
                ,axis=1
                )

        # export the resultant dataframe to excel
        # self.input_df.to_excel("./df1.xlsx", header=None, index=None) # first_pass()

if __name__ == '__main__':
    tmmi = TestMethodMismatchIdentification()
    tmmi.execute()
