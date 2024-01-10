import { addMovieToRadarr } from "./main.js";
import { sendPredefinedMessage } from "./chat.js";

var lastMousePosition = { x: 0, y: 0 };

export function showPersonPopover(element) {
  var popoverTimeout;
  var isMouseOverPopover = true;

  // Initialize the popover
  if (!$(element).data("bs.popover")) {
    $(element).popover({
      trigger: "manual",
      placement: function (context, source) {
        return customPopoverPlacement(context, source);
      },
      title: "Person Details",
      content: "Loading details...",
      html: true,
    });
  }

  // Click event to show popover
  $(element)
    .off("click")
    .on("click", function () {
      var personName = $(element).text().trim();
      fetch(`/person_details/${encodeURIComponent(personName)}`)
        .then((response) => response.json())
        .then((data) => {
          var imagePath = data.profile_path
            ? `https://image.tmdb.org/t/p/original${data.profile_path}`
            : "static/no_photo_image.jpg";
          var biography = data.biography || "No biography available";
          var shortBio =
            biography.length > 200
              ? biography.substring(0, 200) + "..."
              : biography;
          const fullCredits = data.movie_credits
            .slice(5) // Start from the 6th element
            .map(
              (credit) =>
                `<dd><a class="movie-credit-link" data-movie-title="${credit.title}" href="javascript:void(0);">${credit.title} (${credit.release_year})</a></dd>`
            )
            .join("");
          $(element).data("fullCredits", fullCredits);

          // Display initial subset of credits
          console.log("Here is data.movie_credits: ", data.movie_credits);
          const maxDisplayCredits = 5; // Number of movie credits to show initially
          let displayedCredits = data.movie_credits
            .slice(0, maxDisplayCredits) // Take the first 5 elements
            .map(
              (credit) =>
                `<dd><a class="movie-credit-link" data-movie-title="${credit.title}" href="javascript:void(0);">${credit.title} (${credit.release_year})</a></dd>`
            )
            .join("");

          let creditsHtml = `<dl><dt>Movie Credits:</dt>${displayedCredits}</dl>`;
          if (data.movie_credits.length > maxDisplayCredits) {
            creditsHtml += `<dd><span id="more-credits" class="more-link">More...</span></dd>`;
          }

          var imageTag = `<img src="${imagePath}" alt="${data.name} Photo" class="img-fluid" style="width: 185px; height: 278px;">`;

          var buttonsHtml = `
              <div style="text-align: right; padding-top: 10px; display: flex; justify-content: flex-end;">
                <button type="button" class="btn popover-button ask-moviebot-person" data-person-name="${data.name}" style="margin-left: 5px;">Ask MovieBot</button>
                <button type="button" class="btn popover-button btn-imdb-person" data-person-imdb-id="${data.imdb_id}" style="margin-left: 5px;">IMDb</button>
                <button type="button" class="btn popover-button btn-wiki-person" data-wiki-url="" style="margin-left: 5px;">Wiki</button>
                
              </div>`;

          var contentHtml = `
          <div class="movie-title">${data.name}</div>
          <div class="movie-details-card">
            
            <div class="movie-poster">${imageTag}</div>
            <div class="movie-div">
              <div class="movie-info">
                <p><dt>Birthday:</dt> ${data.birthday || "N/A"}</p>
                <p>${creditsHtml}<p>
                <p><dt>Biography:</dt> <span id="short-bio">${shortBio}</span>
                ${
                  biography.length > 200
                    ? `<span id="more-bio" class="more-link">More</span>`
                    : ""
                }
            
              </div>
              <div class="movie-buttons" style="display: flex;">
                ${buttonsHtml}
              </div>
            </div>
            
            
          </div>`;

          $(element).data("fullBiography", data.biography);
          $(element).data("bs.popover").config.content = contentHtml;
          $(element).popover("show");

          $(".btn-imdb-person").attr("data-person-imdb-id", data.imdb_id);
          $(".btn-wiki-person").attr("data-wiki-url", data.wiki_url);
          $(".ask-moviebot-person").attr("data-person-name", data.name);
          $(".movie-credit-link").each(function (index) {
            // Ensure index is within the range of the data.movie_credits array
            if (index < data.movie_credits.length) {
              $(this).attr("data-movie-title", data.movie_credits[index].title);
            }
          });
          console.log(
            "Here is the data.movie_creditssssssss: ",
            data.movie_credits
          );
        })
        .catch((error) => {
          console.error("Error:", error);
          $(element).data("bs.popover").config.content =
            "Details not available";
          $(element).popover("show");
        });
    });

  // Function to hide popover on mouseleave
  function hidePopover() {
    setTimeout(function () {
      if (!isMouseOverPopover) {
        $(element).popover("hide");
      }
    }, 200); // Delay of 200ms
  }

  // Event binding for mouseleave on the triggering element
  $(element)
    .off("mouseleave")
    .on("mouseleave", function () {
      popoverTimeout = setTimeout(hidePopover, 200);
    });

  // Event binding for mouseleave on the triggering element
  $(element)
    .off("mouseleave")
    .on("mouseleave", function () {
      var $element = $(this);
      var elementRect = this.getBoundingClientRect();

      popoverTimeout = setTimeout(function () {
        console.log("Mouse left the source element");
        // Check if the mouse is not over the source and not over the popover
        if (
          lastMousePosition.x < elementRect.left ||
          lastMousePosition.x > elementRect.right ||
          lastMousePosition.y < elementRect.top ||
          lastMousePosition.y > elementRect.bottom
        ) {
          $element.popover("hide");
        }
      }, 200); // Delay of 350ms
    });
  // Event binding for popover shown event
  $(element)
    .off("shown.bs.popover")
    .on("shown.bs.popover", function () {
      var popoverId = $(element).attr("aria-describedby");
      var $popover = $("#" + popoverId);

      $popover
        .on("mouseenter", function () {
          isMouseOverPopover = true;
          clearTimeout(popoverTimeout);
        })
        .on("mouseleave", function () {
          isMouseOverPopover = false;
          popoverTimeout = setTimeout(hidePopover, 200);
        });

      $popover
        .off("click", ".ask-moviebot-person")
        .on("click", ".ask-moviebot-person", function () {
          var personName = $(this).data("person-name");
          if (personName) {
            sendPredefinedMessage(`Tell me about ${personName}`);
          } else {
            console.log("Person name not found for MovieBot");
          }
        });

      // Assuming $popover is a static ancestor that contains the dynamic .movie-credit-link elements

      $popover.on("click", ".btn-imdb-person", function () {
        var imdbId = $(this).data("person-imdb-id");
        console.log("Clicked person IMDb ID: ", imdbId);
        if (imdbId) {
          window.open(`https://www.imdb.com/name/nm${imdbId}`, "_blank");
        } else {
          console.log("IMDb ID for person not found");
        }
      });

      $popover.on("click", ".btn-wiki-person", function () {
        var wikiUrl = $(this).data("wiki-url");
        console.log("WWWWWWWWWWWWWWWWWWIKI URLL::::::::::: ", wikiUrl);
        if (wikiUrl) {
          window.open(wikiUrl, "_blank");
        } else {
          console.log("Wikipedia URL for person not found");
        }
      });

      $popover.find("#more-bio").on("click", function () {
        var fullBiography = $(element).data("fullBiography");
        $popover.find("#short-bio").text(fullBiography);
        $(this).remove(); // Remove the 'More' button
      });

      $popover.find("#more-credits").on("click", function () {
        $(this).css("color", "green"); // Example: changing the color to green
        $(this).text("Asking MovieBot"); // Temporarily change the link text
        var fullCreditsHtml = `${$(element).data("fullCredits")}</dl>`;
        $(this).parent().replaceWith(fullCreditsHtml); // Replace the dd with full credits
        $(this).remove(); // Remove the 'More' link
      });

      $popover.on("click", ".movie-credit-link", function () {
        // Store the original text of the link
        var originalText = $(this).text();

        // Temporarily change the link text and style to indicate action
        $(this).text("Asking MovieBot");
        $(this).addClass("clicked-style"); // Add a class to change color and font weight

        // Add your logic here to ask MovieBot about the movie
        var movieTitle = $(this).data("movie-title");

        // Reset the text and style back to the original after some delay
        setTimeout(() => {
          $(this).text(originalText);
          $(this).removeClass("clicked-style"); // Remove the class to revert styles
        }, 2500); // Adjust the time as needed
      });

      $popover.find(".chat-btn").on("click", function () {
        var title = $(this).data("title");
        sendPredefinedMessage(`Tell me more about ${title}.`);
      });

      // Here's the binding for the 'More' button
      $popover
        .find("#more-bio")
        .off("click")
        .on("click", function () {
          var fullBiography = $(element).data("fullBiography");
          $popover.find("#short-bio").text(fullBiography);
          $(this).remove(); // Remove the 'More' button after it's clicked
        });
    });
}

export function setupPopoverHideWithDelay(element) {
  var hideDelay = 200; // Delay in milliseconds
  var hideDelayTimer = null;
  var isMouseOverPopover = false; // New variable to track if the mouse is over the popover

  // Function to update the popover content once details are loaded
  function updatePopoverContent(data) {
    function createPersonSpans(names, group) {
      const maxDisplay = 3; // Number of names to display initially
      let displayedNamesHtml = names
        .slice(0, maxDisplay)
        .map((name) => `<span class="person-link">${name.trim()}</span>`)
        .join(", ");

      let hiddenNamesHtml = "";
      if (names.length > maxDisplay) {
        hiddenNamesHtml = names
          .slice(maxDisplay)
          .map(
            (name) =>
              `<span class="person-link" style="display: none;">${name.trim()}</span>`
          )
          .join(", ");
      }

      let moreButtonHtml =
        names.length > maxDisplay
          ? `<span id="toggle-${group}" class="more-toggle">More</span>`
          : "";

      return `<span id="displayed-${group}">${displayedNamesHtml}</span><span id="more-${group}" style="display: none;">${hiddenNamesHtml}</span>${moreButtonHtml}`;
    }
    console.log("Here is the data:", data);
    console.log("Here is the imdb_id: ", data.imdb_id);
    console.log("Here is the wiki_url: ", data.wiki_url);
    var buttonsHtml = `
      <div style="text-align: right; padding-top: 10px; display: flex; justify-content: left;">
        <button type="button" class="btn popover-button add-to-radarr" data-tmdb-id="${data.tmdb_id}">Add to Radarr</button>
        <button type="button" class="btn popover-button ask-moviebot" data-movie-title="${data.title}">Ask MovieBot</button>
        <button type="button" class="btn popover-button btn-imdb" data-imdb-id="${data.imdb_id}" style="margin-left: 5px;">IMDb</button>
        <button type="button" class="btn popover-button btn-wiki" data-wiki-url="${data.wiki_url}" style="margin-left: 5px;">Wiki</button>
      </div>`;

    var contentHtml = `
      <div class="movie-title">${data.title}</div>
      <div class="movie-details-card">
        <div class="movie-poster">
          <img src="https://image.tmdb.org/t/p/original${
            data.poster_path
          }" alt="${data.title} Poster" class="img-fluid">
        </div>
        <div class="movie-div">
          <div class="movie-info">       
            <p class="movie-director"><strong>Director: </strong>${createPersonSpans(
              data.director.split(","),
              "director"
            )}</p>
            <p class="movie-dop"><strong>DoP: </strong>${createPersonSpans(
              data.dop.split(","),
              "dop"
            )}</p>
            <p class="movie-writers"><strong>Writers: </strong>${createPersonSpans(
              data.writers.split(","),
              "writers"
            )}</p>
            <p class="movie-stars"><strong>Stars: </strong>${createPersonSpans(
              data.stars.split(","),
              "stars"
            )}</p>
            <p class="movie-rating"><strong>TMDb Rating: </strong>${
              data.vote_average
            }</p>
            <p class="movie-release-date"><strong>Release Date: </strong>${
              data.release_date
            }</p>
            <p class="movie-description"><strong>Description: </strong>${
              data.description
            }</p>  
          </div>
          <div class="buttons" style="display: flex;">
            ${buttonsHtml}
          </div>
        </div>
      </div>`;
    $(element).data("bs.popover").config.content = contentHtml;
    $(element).popover("show");
    $(element).popover("update");

    rebindEventHandlers();

    $(".btn-wiki").attr("data-wiki-url", data.wiki_url);

    $(".btn-imdb").attr("data-imdb-id", data.imdb_id);

    $(document)
      .off("click", ".ask-moviebot")
      .on("click", ".ask-moviebot", function () {
        var movieTitle = $(this).data("movie-title");
        sendPredefinedMessage(`Tell me about ${data.title}`);
      });

    $(document)
      .off("click", ".add-to-radarr")
      .on("click", ".add-to-radarr", function () {
        var tmdbId = $(this).data("tmdb-id");
        addMovieToRadarr(data.tmdb_id);
      });

    // Setup mouseover event for each person link
    $(".person-link").on("mouseover", function () {
      showPersonPopover(this);
    });
  }

  $(document).on("click", ".popover-button", function () {
    // Handle the button click event
    console.log("Popover button clicked");
    // Add your custom logic here
  });

  $(document).on("click", ".btn-wiki", function () {
    var wikiUrl = $(this).data("wiki-url");
    if (wikiUrl) {
      window.open(wikiUrl, "_blank");
    } else {
      console.log("Wikipedia URL not found");
    }
  });

  // Track mouse position
  $(document).on("mousemove", function (event) {
    lastMousePosition.x = event.pageX;
    lastMousePosition.y = event.pageY;
  });

  var showPopover = function () {
    clearTimeout(hideDelayTimer);
    closeAllPopovers(); // Close all other open popovers

    var $element = $(element);
    var tmdbId = $element.data("tmdb-id");

    $.get(`/movie_details/${tmdbId}`, function (data) {
      updatePopoverContent(data); // Update the popover content

      // Schedule to show the popover after a brief delay
      setTimeout(function () {
        var popover = $element.data("bs.popover").getTipElement();
        if (popover) {
          var popoverRect = popover.getBoundingClientRect();
          // Check if the mouse is over the popover
          if (
            lastMousePosition.x >= popoverRect.left &&
            lastMousePosition.x <= popoverRect.right &&
            lastMousePosition.y >= popoverRect.top &&
            lastMousePosition.y <= popoverRect.bottom
          ) {
            isMouseOverPopover = true;
            $element.popover("show");
          }
        }
      }, 200); // Delay of 200ms to allow popover to render and position
    }).fail(function () {
      $element.data("bs.popover").config.content = "Failed to load details.";
      $element.popover("show");
    });
  };

  // Updated hidePopover function
  var hidePopover = function () {
    // Delay the hide check to allow time for the mouse to be detected over the popover
    setTimeout(function () {
      if (!isMouseOverPopover) {
        var popover = $(element).data("bs.popover").getTipElement();
        var popoverRect = popover.getBoundingClientRect();
        var buffer = 10; // 10 pixels buffer

        // Check if the mouse is within the buffer area around the popover
        if (
          lastMousePosition.x < popoverRect.left - buffer ||
          lastMousePosition.x > popoverRect.right + buffer ||
          lastMousePosition.y < popoverRect.top - buffer ||
          lastMousePosition.y > popoverRect.bottom + buffer
        ) {
          $(element).popover("hide");
        } else {
          setTimeout(hidePopover, 200); // Check again after a short delay
        }
      }
    }, 200); // A brief delay, adjust as needed
  };

  // When mouse enters the popover, set isMouseOverPopover to true
  $("body").on("mouseenter", ".popover", function () {
    isMouseOverPopover = true;
  });

  // When mouse leaves the popover, set isMouseOverPopover to false and start the hide delay
  $("body").on("mouseleave", ".popover", function () {
    isMouseOverPopover = false;
    hideDelayTimer = setTimeout(hidePopover, hideDelay);
  });

  $(document).on("click", ".btn-imdb", function () {
    var imdbId = $(this).data("imdb-id");
    if (imdbId) {
      window.open(`https://www.imdb.com/title/tt${imdbId}`, "_blank");
    } else {
      console.log("IMDbbbbb ID not found");
    }
  });

  $(element)
    .popover({
      trigger: "manual",
      html: true,
      placement: function (context, source) {
        return customPopoverPlacement(context, source);
      },
      container: "body",
      content: "Loading details...",
      offset: 10,
      delay: { show: 1, hide: hideDelay },
    })
    .on("mouseenter", function () {
      var $element = $(this);
      var elementRect = this.getBoundingClientRect();

      setTimeout(function () {
        // Check if the current mouse position is within the bounds of the source element
        if (
          lastMousePosition.x >= elementRect.left &&
          lastMousePosition.x <= elementRect.right &&
          lastMousePosition.y >= elementRect.top &&
          lastMousePosition.y <= elementRect.bottom
        ) {
          showPopover.call($element); // Show the popover
        }
      }, 200); // 500 milliseconds delay
    });
  $(element).on("mouseleave", function () {
    var $element = $(this);
    var elementRect = this.getBoundingClientRect(); // Define elementRect here

    console.log("Mouse left the source element");
    setTimeout(function () {
      // Check if the mouse is not over the source and not over the popover
      if (
        lastMousePosition.x < elementRect.left ||
        lastMousePosition.x > elementRect.right ||
        lastMousePosition.y < elementRect.top ||
        lastMousePosition.y > elementRect.bottom
      ) {
        if (!isMouseOverPopover) {
          $element.popover("hide");
        }
      }
    }, 200); // Delay of 500ms
  });

  $("body")
    .on("mouseenter", ".popover", function () {
      isMouseOverPopover = true;
    })
    .on("mouseleave", ".popover", function () {
      isMouseOverPopover = false;
      hideDelayTimer = setTimeout(function () {
        if (!isMouseOverPopover) {
          $(element).popover("hide");
        }
      }, hideDelay);
    });
}

function customPopoverPlacement(context, source) {
  const wordPosition = $(source).data("word-position");
  const triggerRect = source.getBoundingClientRect();
  const popoverHeight = $(context).outerHeight();
  const windowHeight = window.innerHeight;

  const spaceTop = triggerRect.top;
  const spaceBottom = windowHeight - triggerRect.bottom;

  // Check if the popover fits on top or bottom, is not off the viewport, and doesn't cover the source
  const fitsTop = spaceTop >= popoverHeight;
  const fitsBottom = spaceBottom >= popoverHeight;

  // Determine the placement based on the word position
  const placement = wordPosition < triggerRect.width / 2 ? "bottom" : "top";

  // Create an array of placements that can fit the popover
  const placements = [
    { side: placement, space: fitsBottom ? spaceBottom : 0 },
    {
      side: placement === "bottom" ? "top" : "bottom",
      space: fitsTop ? spaceTop : 0,
    },
  ];

  // Filter out placements that would cover the source
  const validPlacements = placements.filter((placement) => placement.space > 0);

  // If there are no valid placements, default to the calculated placement
  if (validPlacements.length === 0) {
    return placement;
  }

  // Sort the placements by the available space
  validPlacements.sort((a, b) => b.space - a.space);

  // Return the placement with the most space
  return validPlacements[0].side;
}

function rebindEventHandlers() {
  // Unbind and rebind event handlers for dynamic content

  // For .ask-moviebot button
  $(document)
    .off("click", ".ask-moviebot")
    .on("click", ".ask-moviebot", function () {
      var movieTitle = $(this).data("movie-title");
      sendPredefinedMessage(`Tell me about the movie ${movieTitle}`);
    });

  // For .add-to-radarr button
  $(document)
    .off("click", ".add-to-radarr")
    .on("click", ".add-to-radarr", function () {
      var tmdbId = $(this).data("tmdb-id");
      addMovieToRadarr(tmdbId);
    });

  // For .person-link elements
  $(".person-link")
    .off("mouseover")
    .on("mouseover", function () {
      showPersonPopover(this);
    });

  // Add other dynamic elements' event handlers here
}

// Function to close all open popovers
function closeAllPopovers() {
  $('[data-toggle="popover"]').each(function () {
    $(this).popover("hide");
  });
}

$(document)
  .off("click", ".movie-credit-link")
  .on("click", ".movie-credit-link", function () {
    var movieTitle = $(this).data("movie-title");
    console.log("Movie title clicked:", movieTitle);
    if (movieTitle) {
      sendPredefinedMessage(`Tell me about the movie "${movieTitle}".`);
    } else {
      console.log("Movie title not found");
    }
  });

$(document).on("click", ".more-toggle", function () {
  let group = this.id.split("-")[1];
  let moreSpan = $(`#more-${group}`);

  // Toggle the visibility
  moreSpan.toggle();

  // Update button text based on the visibility of moreSpan
  $(this).text(moreSpan.is(":visible") ? "Less" : "More");
});

// Update lastMousePosition on mousemove
$(document).on("mousemove", function (event) {
  lastMousePosition.x = event.pageX;
  lastMousePosition.y = event.pageY;
});

// Initialize popovers for each movie link
$(document).ready(function () {
  $('[data-toggle="popover"]').each(function () {
    setupPopoverHideWithDelay(this);
  });
});

$(document).on("mousemove", ".movie-title", function (event) {
  lastMousePosition = { x: event.pageX, y: event.pageY };
});
