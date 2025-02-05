#!/usr/bin/env python3

"""
Collect information about all commits in the set of repositories/branches.

This uses `repos.yaml`
This generates the files `commits/**`.
"""

import os
import sys
from datetime import datetime

import requests

import yaml

with open('github.yaml') as h:
    data = yaml.safe_load(h.read())
assert 'token' in data
assert data['token']

headers = {'Authorization': data['token']}


def get_commits(owner_name, repo_name, branch):  # noqa: D103
    commits = []
    history_args = ''
    while True:
        query = """
{
  repository(name: "%s", owner: "%s") {
    ref(qualifiedName: "%s") {
      target {
        ... on Commit {
          id
          history(first: 100%s) {
            pageInfo {
              hasNextPage
              endCursor
            }
            edges {
              node {
                author {
                  user {
                    login
                  }
                  avatarUrl(size: 16)
                }
                authoredDate
              }
            }
          }
        }
      }
    }
  }
}""" % (repo_name, owner_name, branch, history_args)

        result = run_query(query)

        if result['data']['repository'] is None:
            raise RuntimeError(
                f'Repo https://github.com/{owner_name}/{repo_name} does not '
                'exist')
        if result['data']['repository']['ref'] is None:
            raise RuntimeError(
                f'Branch {branch} does not exist in repo https://github.com/'
                f'{owner_name}/{repo_name}')
        history = result['data']['repository']['ref']['target']['history']

        for edge in history['edges']:
            node = edge['node']

            commits.append({
                'author': (
                    node['author']['user']['login']
                    if node['author']['user'] is not None else None),
                'avatarUrl': node['author']['avatarUrl'],
                'authoredDate': datetime.strptime(
                    node['authoredDate'], '%Y-%m-%dT%H:%M:%SZ').timestamp(),
            })

        if not history['pageInfo']['hasNextPage']:
            break
        history_args = ', after: "%s"' % history['pageInfo']['endCursor']
    return commits


def run_query(query):  # noqa: D103
    request = request = requests.post(
        'https://api.github.com/graphql',
        json={'query': query}, headers=headers)

    if request.status_code != 200:
        raise Exception(
            'Query failed to run by returning code of {}. {}'
            .format(request.status_code, query))
    return request.json()


with open('repos.yaml', 'r') as h:
    repos = yaml.safe_load(h)

print(
    len(repos), 'repos with',
    sum(len(versions) for versions in repos.values()), 'branches')

repo_progress = 0
fetched_commit_count = 0
for url, versions in repos.items():
    owner_name, repo_name = url.split('/', 1)
    for branch, distros in versions.items():
        yaml_file = f'data/commits/{owner_name}/{repo_name}/{branch}.yaml'
        if os.path.exists(yaml_file):
            print('.', end='')
            sys.stdout.flush()
            continue

        # print('\n', owner_name, repo_name, branch)
        try:
            commits = get_commits(owner_name, repo_name, branch)
        except RuntimeError as e:
            print()
            distros_str = ' '.join(distros)
            print(str(e), f'[{distros_str}]', file=sys.stderr)
            continue
        commits.sort(key=lambda c: c['authoredDate'])

        print('*', end='')
        sys.stdout.flush()

        os.makedirs(os.path.dirname(yaml_file), exist_ok=True)
        with open(yaml_file, 'w') as h:
            yaml.dump(commits, h)
        fetched_commit_count += len(commits)
    # only one repo at a time
    # if fetched_commit_count:
    #     break
    repo_progress += 1
    if repo_progress % 100 == 0:
        print()
        print(f'{repo_progress} done')

print()
print(fetched_commit_count, 'commit info fetched')
