package main

import (
	"github.com/labstack/echo/v4"
	"github.com/labstack/echo/v4/middleware"
	"soc-backend/gitinterfaces"
	"encoding/json"
	"net/http"
	"html/template"
	"log"
	"os"
	"io"
)

func getJson(url string, target interface{}) error {
	r, err := http.Get(url)
	if err != nil {
		return err
	}
	defer r.Body.Close()

	return json.NewDecoder(r.Body).Decode(target)
}


type Template struct {
    templates *template.Template
}

func (t *Template) Render(w io.Writer, name string, data interface{}, c echo.Context) error {
	return t.templates.ExecuteTemplate(w, name, data)
}


func main() {
	e := echo.New()
	e.Debug = true
	e.Use(middleware.CORS())
	t := &Template{
		templates: template.Must(template.ParseGlob("templates/*.html")),
	}
	e.Renderer = t
	debug := log.New(os.Stdout, "Debug: ", log.LstdFlags)

	e.GET("/elements", func(c echo.Context) error {
		var res gitinterfaces.SearchResponse
		err := getJson("https://api.github.com/search/issues?q=type:pr+author:Glitchyi", &res)
		if err != nil {
			debug.Println("Error fetching JSON:", err)
			// return c.String(http.StatusInternalServerError, "Internal Server Error")
		}
		
		if len(res.Items) == 0 {
			debug.Println("No items found")
		}
		// return c.JSON(http.StatusOK,res.Items)
		return c.Render(http.StatusOK,"elements",map[string]interface{}{
			"items": res.Items,
		})
	})

	e.Logger.Fatal(e.Start(":1323"))
}
