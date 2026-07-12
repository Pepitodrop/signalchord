package streamnormalizer

import (
	"net/url"
	"sort"
	"strings"
)

var tracking = map[string]bool{"utm_source": true, "utm_medium": true, "utm_campaign": true, "utm_term": true, "utm_content": true, "fbclid": true, "gclid": true}

func CanonicalizeURL(raw string) (string, error) {
	u, err := url.Parse(strings.TrimSpace(raw))
	if err != nil {
		return "", err
	}
	u.Fragment = ""
	u.Host = strings.ToLower(u.Host)
	u.Scheme = strings.ToLower(u.Scheme)
	q := u.Query()
	for k := range q {
		if tracking[strings.ToLower(k)] {
			q.Del(k)
		}
	}
	keys := make([]string, 0, len(q))
	for k := range q {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	ordered := url.Values{}
	for _, k := range keys {
		for _, v := range q[k] {
			ordered.Add(k, v)
		}
	}
	u.RawQuery = ordered.Encode()
	if u.Path == "" {
		u.Path = "/"
	}
	return u.String(), nil
}
