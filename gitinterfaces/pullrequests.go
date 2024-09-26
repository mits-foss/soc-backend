package gitinterfaces

// DataExtractor interface defines the method to extract required details
type DataExtractor interface {
    GetRepositoryURL() string
    GetState() string
}

// SearchResponse represents the top-level structure of the JSON data
type SearchResponse struct {
    TotalCount        int    `json:"total_count"`
    IncompleteResults bool   `json:"incomplete_results"`
    Items             []Item `json:"items"`
}

// Item represents each item in the "items" array
type Item struct {
    RepositoryURL string `json:"repository_url"`
    State         string `json:"state"`
}

// GetRepositoryURL returns the repository URL
func (i Item) GetRepositoryURL() string {
    return i.RepositoryURL
}

// GetState returns the state
func (i Item) GetState() string {
    return i.State
}
