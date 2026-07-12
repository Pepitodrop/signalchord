package documentfetcher

import (
	"context"
	"errors"
	"net"
	"net/url"
)

func IsDeniedIP(ip net.IP) bool {
	return ip.IsLoopback() || ip.IsPrivate() || ip.IsUnspecified() || ip.IsLinkLocalUnicast() || ip.IsLinkLocalMulticast()
}

func ValidateFetchURL(raw string) error {
	u, err := url.Parse(raw)
	if err != nil {
		return err
	}
	if u.Scheme != "https" && u.Scheme != "http" {
		return errors.New("unsupported scheme")
	}
	if u.Hostname() == "" || u.User != nil {
		return errors.New("invalid host or userinfo")
	}
	ips, err := net.DefaultResolver.LookupIP(context.Background(), "ip", u.Hostname())
	if err != nil {
		return err
	}
	for _, ip := range ips {
		if IsDeniedIP(ip) {
			return errors.New("private or local address denied")
		}
	}
	return nil
}
