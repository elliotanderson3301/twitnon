#!/usr/bin/env python3
# Copying and distribution of this file, with or without modification,
# are permitted in any medium without royalty. This file is offered
# as-is, without any warranty.

import argparse, bs4, datetime, requests
from pathlib import Path
from tqdm import tqdm
from time import sleep

parser = argparse.ArgumentParser()
parser.add_argument('outfile')
parser.add_argument('-i', '--infile',
                    default=str(Path(__file__).parent / 'accounts.txt'))
parser.add_argument('-d', '--days', type=int, default=7)
args = parser.parse_args()

with open(args.infile) as f:
    accs = [line.strip().rpartition('/')[2]
            for line in f if line.strip()]
accset = {acc.casefold() for acc in accs}

now = datetime.datetime.now()
cutoff = now - datetime.timedelta(days=args.days)

imgs = set()


def tweets(account, cutoff):
    url = f"https://twitter.com/i/profiles/show/{acc}/timeline/tweets"
    params = {}
    might_be_pinned = True
    page_bar = tqdm(desc=f"Pages read ({account})")
    while True:
        page_bar.update()
        resp = requests.get(url, params=params, headers={
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:60.0) '
            'Gecko/20100101 Firefox/60.0'})
        sleep(1)
        try:
            data = resp.json()
        except:
            page_bar.write(f"{account} got {resp.status_code}")
            page_bar.close()
            return
        min_position = data['min_position']
        params['max_position'] = min_position
        html = data['items_html']
        if not html.strip():
            page_bar.close()
            return
        soup = bs4.BeautifulSoup(html, 'html.parser')
        found_something = False
        for tweet in soup.find_all('li', 'stream-item'):
            permalink = tweet.find('a', 'js-permalink')
            if permalink is None:
                page_bar.write("Couldn't find permalink")
                continue
            time = datetime.datetime.fromtimestamp(
                int(permalink.find('span')['data-time']))
            if time < cutoff:
                # We should skip this one
                if ('data-retweet-id' not in tweet.find('div').attrs and
                        not might_be_pinned):
                    # It's not a retweet, so stop looking altogether
                    page_bar.close()
                    return
                continue
            found_something = True
            might_be_pinned = False
            yield tweet
        if not found_something:
            # All we found on this page was old retweets, better abort
            page_bar.close()
            return


image_bar = tqdm(desc="Images found")
acc_bar = tqdm(accs, desc="Accounts")
for acc in acc_bar:
    acc_bar.write(acc)
    for tweet in tweets(acc, cutoff):
        username = tweet.find('div', 'tweet')['data-screen-name']
        follow = username.casefold() in accset
        perma = tweet.find('a', 'js-permalink')
        permalink = f"https://twitter.com{perma['href']}"
        time = datetime.datetime.fromtimestamp(
            int(perma.find('span')['data-time']))
        for i, photo in enumerate(tweet.find_all('div', 'js-adaptive-photo')):
            img_url = photo.find('img')['src']
            identifier = img_url.rpartition('/')[2].partition('.')[0]
            # tweak the time so images appear in order
            imgs.add((time - datetime.timedelta(microseconds=i),
                      f'''<div class="{'follow' if follow else 'nofollow'}" '''
                      f'''data-tweeter="{username}">

<strong><a href="{permalink}">{username}</a></strong><br />
{time}<br />
{identifier}<br />
[<a href="javascript:filterTweeter('{username}');" title="Hide account">X</a>]
[<a href="{img_url}:orig" title="Full image">IMG</a>]
[<a href="{permalink}" title="Source">SRC</a>]<br />
<a href="{img_url}:orig"><img src="{img_url}:thumb" alt="{identifier}" /></a>
<hr />
</div>'''))
            image_bar.update()
acc_bar.close()
image_bar.close()

with open(args.outfile, 'w') as f:
    print(f'''<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"/>
<title>Twitnon report {now}</title>
''''''<style>
div { display: inline-block; width: 160px; font-size: 0.6em; }
div.nofollow { background-color: #ffeeee; }
div.follow { background-color: #eeffee; }
</style>
<script>
function filterTweeter(name) {
    document.querySelectorAll('[data-tweeter="' + name + '"]').forEach(
        function (tweet) {
            tweet.remove();
        }
    )
}
</script>
</head><body>''', file=f)
    for img in sorted(imgs, reverse=True):
        print(img[1], file=f)
    print("<br /><br />Followed accounts are green, retweets are red.", file=f)
    acclist = ', '.join(f'<a href="https://twitter.com/{acc}">{acc}</a>'
                        for acc in accs)
    print(f"""<br /> <br />
Followed accounts: {acclist}""", file=f)
    print('''<br /><br />
<a href="https://github.com/hushbugger/twitnon">Source code</a>
</body></html>''', file=f)
