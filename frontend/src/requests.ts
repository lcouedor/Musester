import axios from "axios";

const BASE_URL: string = "http://127.0.0.1:5000/";

export const auth = async (
//   username: string,
//   password: string
): Promise<any> => {
    let response;

    console.log("auth");
    
    try {
        response = await axios.get(`${BASE_URL}login`);
    } catch (error) {
        return error;
    }

    return response;
};

export const get = async (url: string, username: string, password: string, data: any = {}): Promise<any> => {
    let response;

    try {
        response = await axios.get(`${BASE_URL}${url}`, {
            headers: {
                AuthorizationUser: username,
                AuthorizationPassword: password,
            },
            params: data,
        });
    } catch (error) {
        return error;
    }

    return response;
}

export default auth;