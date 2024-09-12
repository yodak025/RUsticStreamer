const usernameInput = document.getElementById('username-input');
const usernameField = document.getElementById('username');
const submitUsernameBtn = document.getElementById('submit-username');
const menu = document.getElementById("menu");
const streamersBtn = document.getElementById("streamers-btn");
const videos = document.getElementById("video-container");
const selected_video = document.getElementById("video-player");

var client_name;

submitUsernameBtn.addEventListener('click', function () {
    username = usernameField.value;
    client_register(username);
})

streamersBtn.addEventListener("click", function() {
    return fetch('/options', {
        body: JSON.stringify ({
            client_id: client_name,
            content: {content: 'None'}
        }),
        headers: {
            'Content-Type': 'aplication/json'
        },
        method: 'POST'
    }).then(function(response) {
        return response.json();
        }).then(function(answer) {
            loadJSONDB(answer);
            videos.style.display = 'block';
            streamersBtn.disabled = true;
        })
    
})

function loadJSONDB(json_msg) {
    let streamers = json_msg.streamers;
    for (let i = 0; i < streamers.length; i++) {
        (function(index) {
          let div = document.createElement("div");
          div.classList.add("video");
          let h2 = document.createElement("h2");
          h2.textContent = streamers[index].name;
          h2.addEventListener("click", function() {
            videos.style.display = 'none';
            selected_video.style.display = 'block';
            send_streamers(client_name, streamers[index].address);
          });
          div.appendChild(h2);
          videos.appendChild(div);
        })(i);
      }
}

function client_register(name) {
    return fetch('/register', {
        body: JSON.stringify ({
            client_id: name,
            content: {content: 'None'}
        }),
        headers: {
            'Content-Type': 'aplication/json'
        },
        method: 'POST'
    }).then(function(response) {
        return response.json();
        }).then(function(answer) {
            if (answer.request === 'accepted') {
                client_name = name
                menu.style.display = 'block';
                usernameInput.style.display = 'none';
            }
            else if (answer.request === 'denied' || name === '') {
                usernameInput.style.display = 'block'
            }
        })
    };

function send_streamers(name, addr) {
        return fetch('/streamer', {
            body: JSON.stringify ({
                client_id: name,
                content: {address: addr}
            }),
            headers: {
                'Content-Type': 'plain/text'
            },
            method: 'POST'
        }).then(function(response) {
            return response.json();
            })};



            var pc = null;

//Video Code
function negotiate() {
    pc.addTransceiver('video', {direction: 'recvonly'});
    pc.addTransceiver('audio', {direction: 'recvonly'});
    return pc.createOffer().then(function(offer) {
        return pc.setLocalDescription(offer);
    }).then(function() {
        // wait for ICE gathering to complete
        return new Promise(function(resolve) {
            if (pc.iceGatheringState === 'complete') {
                resolve();
            } else {
                function checkState() {
                    if (pc.iceGatheringState === 'complete') {
                        pc.removeEventListener('icegatheringstatechange', checkState);
                        resolve();
                    }
                }
                pc.addEventListener('icegatheringstatechange', checkState);
            }
        });
    }).then(function() {
        var offer = pc.localDescription;
        return fetch('/offer', {
            body: JSON.stringify({
                client_id: client_name,
                content:{
                sdp: offer.sdp,
                type: offer.type,
            }}),
            headers: {
                'Content-Type': 'application/json'
            },
            method: 'POST'
        });
    }).then(function(response) {
        return response.json();
    }).then(function(answer) {
        return pc.setRemoteDescription(answer);
    }).catch(function(e) {
        alert(e);
    });
}

function start() {
    var config = {
        sdpSemantics: 'unified-plan'
    };

    if (document.getElementById('use-stun').checked) {
        config.iceServers = [{urls: ['stun:stun.l.google.com:19302']}];
    }

    pc = new RTCPeerConnection(config);

    // connect audio / video
    pc.addEventListener('track', function(evt) {
        if (evt.track.kind == 'video') {
            document.getElementById('video').srcObject = evt.streams[0];
        } else {
            document.getElementById('audio').srcObject = evt.streams[0];
        }
    });

    document.getElementById('start').style.display = 'none';
    negotiate();
    document.getElementById('stop').style.display = 'inline-block';
}

function stop() {
    document.getElementById('stop').style.display = 'none';

    // close peer connection
    setTimeout(function() {
        pc.close();
    }, 500);
}